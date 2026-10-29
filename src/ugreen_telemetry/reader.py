"""Isolated host SMART sampler for the UGOS Compose project."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .file_gate import FileChangeGate


LOG = logging.getLogger(__name__)
DISK = re.compile(r"/dev/sd[a-z]+\Z")
VOLUME = re.compile(r"/host/volume[1-9][0-9]*\Z")
STOP = False


def _stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def valid_targets(data: object, sys_root: Path = Path("/host/sys")) -> dict[str, object]:
    if not isinstance(data, dict) or not {"devices", "volumes"} <= set(data) or set(data) - {"devices", "volumes", "interval_seconds", "volume_interval_seconds"}:
        raise ValueError("Invalid target configuration")
    interval = data.get("interval_seconds", 900)
    if type(interval) is not int or not 300 <= interval <= 59940:
        raise ValueError("Invalid storage sampling interval")
    volume_interval = data.get("volume_interval_seconds", 900)
    if type(volume_interval) is not int or not 60 <= volume_interval <= 59940:
        raise ValueError("Invalid volume sampling interval")
    devices, volumes = data["devices"], data["volumes"]
    if not isinstance(devices, list) or len(devices) > 24 or any(not isinstance(disk, str) for disk in devices) or len(set(devices)) != len(devices):
        raise ValueError("Invalid disk selection")
    for disk in devices:
        if not isinstance(disk, str) or not DISK.fullmatch(disk):
            raise ValueError("Invalid disk path")
        if not (sys_root / "block" / Path(disk).name / "queue" / "rotational").exists():
            raise ValueError("Selected disk is absent")
    if not isinstance(volumes, dict) or len(volumes) > 8:
        raise ValueError("Invalid volume selection")
    for label, path in volumes.items():
        if not isinstance(label, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,19}", label):
            raise ValueError("Invalid volume label")
        if not isinstance(path, str) or not VOLUME.fullmatch(path):
            raise ValueError("Volume path must be a mounted host volume")
    return data


def write_empty_snapshot(path: Path) -> None:
    data = {"version": 2, "sampled_at": int(time.time()), "hdd_count": 0,
            "readings": [], "volume_count": 0, "volumes": []}
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".smart-", delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _sample_part(targets: dict[str, object], devices: bool, volumes: bool,
                 workdir: Path = Path("/tmp")) -> dict[str, object]:
    helper_targets = {
        "devices": targets["devices"] if devices else [],
        "volumes": targets["volumes"] if volumes else {},
    }
    if not helper_targets["devices"] and not helper_targets["volumes"]:
        return {"sampled_at": int(time.time()), "hdd_count": 0, "readings": [],
                "volume_count": 0, "volumes": []}
    validated_path = workdir / "validated-targets.json"
    output_path = workdir / "part-snapshot.json"
    validated_path.write_text(json.dumps(helper_targets, separators=(",", ":")), encoding="utf-8")
    os.chmod(validated_path, 0o600)
    output_path.unlink(missing_ok=True)
    result = subprocess.run(
        ["python", "/opt/ugreen/host-smart-snapshot.py", "--config", str(validated_path),
         "--sys-root", "/host/sys", "--device-root", "/host/dev", "--device-type", "sat",
         "--smartctl", "/usr/sbin/smartctl", "--output", str(output_path)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"Snapshot helper failed: exit={result.returncode}")
    if result.returncode == 1:
        LOG.debug("Sample incomplete; a disk may be sleeping or unsupported")
    return json.loads(output_path.read_text(encoding="utf-8"))


def _write_combined_snapshot(path: Path, disk: dict[str, object], volume: dict[str, object]) -> None:
    data = {"version": 3, "sampled_at": int(time.time()),
            "disk_sampled_at": disk["sampled_at"], "volume_sampled_at": volume["sampled_at"],
            "hdd_count": disk["hdd_count"], "readings": disk["readings"],
            "volume_count": volume["volume_count"], "volumes": volume["volumes"]}
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".smart-", delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    targets_path = Path(os.environ.get("TARGETS_FILE", "/data/targets.json"))
    disk_interval = int(os.environ.get("HDD_INTERVAL_SECONDS", "900"))
    if not 300 <= disk_interval <= 86400:
        raise SystemExit("Invalid sampling interval")
    targets_gate = FileChangeGate(targets_path)
    next_disk = 0.0
    next_volume = 0.0
    disk_sample: dict[str, object] = {"sampled_at": 0, "hdd_count": 0, "readings": []}
    volume_sample: dict[str, object] = {"sampled_at": 0, "volume_count": 0, "volumes": []}
    while not STOP:
        try:
            now = time.monotonic()
            previous_mtime = targets_gate.mtime
            if targets_gate.due(now, min(next_disk, next_volume)):
                targets = valid_targets(json.loads(targets_path.read_text(encoding="utf-8")))
                changed = targets_gate.mtime != previous_mtime
                disk_interval = targets.get("interval_seconds", disk_interval)
                volume_interval = targets.get("volume_interval_seconds", 900)
                if changed or now >= next_disk:
                    try:
                        disk_sample = _sample_part(targets, devices=True, volumes=False)
                    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                        LOG.warning("Could not sample selected disks: %s", exc)
                        disk_sample = {"sampled_at": int(time.time()), "hdd_count": 0, "readings": []}
                    next_disk = time.monotonic() + disk_interval
                if changed or now >= next_volume:
                    try:
                        volume_sample = _sample_part(targets, devices=False, volumes=True)
                    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                        LOG.warning("Could not sample selected volumes: %s", exc)
                        volume_sample = {"sampled_at": int(time.time()), "volume_count": 0, "volumes": []}
                    next_volume = time.monotonic() + volume_interval
                _write_combined_snapshot(Path("/snapshots/telemetry.json"), disk_sample, volume_sample)
        except FileNotFoundError:
            next_disk = time.monotonic() + disk_interval  # The wizard has not selected targets yet.
            next_volume = time.monotonic() + 900
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            LOG.warning("Could not sample selected targets: %s", exc)
            next_disk = time.monotonic() + disk_interval
            next_volume = time.monotonic() + 900
        for _ in range(10):
            if STOP:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
