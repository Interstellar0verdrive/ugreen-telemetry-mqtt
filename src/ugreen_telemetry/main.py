from __future__ import annotations

import logging
import json
import os
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

from .config import load_config
from .file_gate import FileChangeGate
from .mqtt import TelemetryPublisher
from .sensors import HostCollector, Reading, read_smart_snapshot


LOG = logging.getLogger("ugreen_telemetry")


def reading_group(key: str) -> str:
    if key == "cpu_usage":
        return "cpu"
    if key == "memory_usage":
        return "memory"
    if key == "cpu_temperature":
        return "cpu_temperature"
    if key == "uptime":
        return "uptime"
    if key.startswith("volume_"):
        return "volume"
    if key.startswith("nvme_") or key.startswith("ssd_"):
        return "nvme"
    if key.startswith("hdd_") and not key.endswith("_temperature"):
        return "diagnostics"
    return "hdd"


def _selected(readings: dict[str, Reading], groups: set[str]) -> dict[str, Reading]:
    return {key: reading for key, reading in readings.items() if reading_group(key) in groups}


def group_intervals(raw: str | None, fast: int, slow: int, storage: int, volume: int) -> dict[str, int]:
    defaults = {"cpu": fast, "memory": fast, "cpu_temperature": slow,
                "uptime": slow, "volume": volume, "hdd": storage,
                "nvme": storage, "diagnostics": storage}
    if raw is None:
        return defaults
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != set(defaults) or any(
        type(value) is not int or not (5 if group in {"hdd", "nvme", "diagnostics"} else 1) <= value <= 999
        for group, value in data.items()
    ):
        raise ValueError("Invalid group intervals")
    return {group: minutes * 60 for group, minutes in data.items()}


def _group_readings(group: str, fast: dict[str, Reading], slow: dict[str, Reading],
                    storage: dict[str, Reading], now: float, fast_at: float, slow_at: float,
                    storage_at: float, fast_interval: int, slow_interval: int,
                    storage_interval: int, volume_interval: int) -> dict[str, Reading]:
    if group == "nvme":
        result = {}
        if slow_at and now - slow_at <= 2 * slow_interval:
            result.update(_selected(slow, {"nvme"}))
        if storage_at and now - storage_at <= 2 * storage_interval:
            result.update(_selected(storage, {"nvme"}))
        return result
    if group in {"cpu", "memory"}:
        source, sampled_at, interval = fast, fast_at, fast_interval
    elif group in {"cpu_temperature", "uptime"}:
        source, sampled_at, interval = slow, slow_at, slow_interval
    elif group == "volume":
        source, sampled_at, interval = storage, storage_at, volume_interval
    else:
        source, sampled_at, interval = storage, storage_at, storage_interval
    if not sampled_at or now - sampled_at > 2 * interval:
        return {}
    return {key: reading for key, reading in source.items() if reading_group(key) == group}


def run() -> None:
    from paho.mqtt import client as paho

    cfg = load_config()
    configured_groups = os.environ.get("SENSOR_GROUPS")
    groups = set(configured_groups.split(",")) if configured_groups is not None else None
    intervals = group_intervals(os.environ.get("GROUP_INTERVALS_JSON"), cfg.fast_interval,
                                cfg.slow_interval, cfg.hdd_interval, cfg.volume_interval)
    collector = HostCollector(cfg.proc_root, cfg.sys_root)
    client = paho.Client(
        callback_api_version=paho.CallbackAPIVersion.VERSION2,
        client_id=f"ugreen-telemetry-{cfg.nas_id}",
        protocol=paho.MQTTv5 if cfg.mqtt_protocol == "5" else paho.MQTTv311,
    )
    client.username_pw_set(cfg.mqtt_user, cfg.mqtt_password)
    publisher = TelemetryPublisher(client, cfg.nas_id, cfg.nas_name, uuid.uuid4().hex)
    client.will_set(publisher.status_topic, "offline", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    if cfg.mqtt_tls:
        client.tls_set(ca_certs=cfg.mqtt_ca_file)

    connected = threading.Event()
    stop = threading.Event()
    connection_generation = 0

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        nonlocal connection_generation
        if reason_code == 0:
            connection_generation += 1
            connected.set()
            LOG.info("Connected to MQTT broker")
        else:
            connected.clear()
            LOG.warning("MQTT connection refused: %s", reason_code)

    def on_disconnect(_client, _userdata, _flags, _reason_code, _properties):
        connected.clear()
        LOG.warning("MQTT connection lost")

    def request_stop(_signum, _frame):
        stop.set()

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    client.connect_async(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
    client.loop_start()

    fast_cache: dict[str, Reading] = {}
    slow_cache: dict[str, Reading] = {}
    hdd_cache: dict[str, Reading] = {}
    fast_sample_at = 0.0
    slow_sample_at = 0.0
    hdd_sample_at = 0.0
    next_fast = 0.0
    next_slow = 0.0
    next_hdd = 0.0
    next_publish = {group: 0.0 for group in intervals}
    snapshot_gate = FileChangeGate(cfg.smart_snapshot_file) if cfg.smart_snapshot_file is not None else None
    coverage_incomplete = False
    published_generation = -1
    try:
        while not stop.is_set():
            now = time.monotonic()
            if now >= next_fast:
                fast_cache = collector.collect_fast()
                if groups is not None:
                    fast_cache = _selected(fast_cache, groups)
                fast_sample_at = now
                next_fast = now + cfg.fast_interval
            if now >= next_slow:
                slow_cache = collector.collect_slow()
                if groups is not None:
                    slow_cache = _selected(slow_cache, groups)
                slow_sample_at = now
                next_slow = now + cfg.slow_interval
            refresh_snapshot = snapshot_gate.due(now, next_hdd) if snapshot_gate else now >= next_hdd
            if (cfg.hdd_enabled or cfg.smart_snapshot_file is not None) and refresh_snapshot:
                scan = (
                    read_smart_snapshot(cfg.smart_snapshot_file, cfg.expected_hdd_count,
                                        2 * cfg.hdd_interval, 2 * cfg.volume_interval)
                    if cfg.smart_snapshot_file is not None
                    else collector.collect_hdd(cfg.expected_hdd_count)
                )
                hdd_cache = _selected(scan.readings, groups) if groups is not None else scan.readings
                hdd_sample_at = now
                next_hdd = now + min(cfg.hdd_interval, cfg.volume_interval)
                if cfg.hdd_enabled:
                    incomplete = scan.hdd_count != cfg.expected_hdd_count or scan.covered_hdds != cfg.expected_hdd_count
                    if incomplete and not coverage_incomplete:
                        LOG.warning(
                            "HDD coverage incomplete: expected=%d found=%d sensors=%d",
                            cfg.expected_hdd_count,
                            scan.hdd_count,
                            scan.covered_hdds,
                        )
                    elif not incomplete and coverage_incomplete:
                        LOG.info("HDD coverage restored")
                    coverage_incomplete = incomplete
            if connected.is_set():
                try:
                    if connection_generation != published_generation:
                        publisher.reconnect()
                        for group in intervals:
                            if groups is None or group in groups:
                                publisher.publish_batch(group, _group_readings(group, fast_cache, slow_cache, hdd_cache,
                                                                                now, fast_sample_at, slow_sample_at,
                                                                                hdd_sample_at, cfg.fast_interval,
                                                                                cfg.slow_interval, cfg.hdd_interval,
                                                                                cfg.volume_interval))
                                next_publish[group] = now + intervals[group]
                        if fast_cache or slow_cache or hdd_cache:
                            publisher.online()
                        else:
                            publisher.offline()
                        published_generation = connection_generation
                    else:
                        any_published = False
                        for group, due_at in next_publish.items():
                            if now >= due_at and (groups is None or group in groups):
                                publisher.publish_batch(group, _group_readings(group, fast_cache, slow_cache, hdd_cache,
                                                                                now, fast_sample_at, slow_sample_at,
                                                                                hdd_sample_at, cfg.fast_interval,
                                                                                cfg.slow_interval, cfg.hdd_interval,
                                                                                cfg.volume_interval))
                                next_publish[group] = now + intervals[group]
                                any_published = True
                        if any_published:
                            if fast_cache or slow_cache or hdd_cache:
                                publisher.online()
                            else:
                                publisher.offline()
                except (OSError, RuntimeError, TimeoutError) as exc:
                    LOG.error("MQTT publication failed: %s", exc)
            stop.wait(1.0)
    finally:
        if connected.is_set():
            try:
                publisher.offline()
            except (OSError, RuntimeError, TimeoutError):
                pass
        client.disconnect()
        client.loop_stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if sys.argv[1:] == ["--probe"]:
        from .probe import print_inventory

        print_inventory(Path(os.environ.get("SYS_ROOT", "/host/sys")))
        return
    if len(sys.argv) > 1:
        LOG.error("Usage: ugreen-telemetry [--probe]")
        raise SystemExit(2)
    try:
        run()
    except (OSError, ValueError) as exc:
        LOG.error("Configuration or startup failed: %s", exc)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
