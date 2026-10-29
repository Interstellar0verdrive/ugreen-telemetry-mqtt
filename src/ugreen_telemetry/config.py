from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}\Z")


@dataclass(frozen=True)
class Config:
    nas_id: str
    nas_name: str
    mqtt_host: str
    mqtt_port: int
    mqtt_user: str
    mqtt_password: str
    mqtt_protocol: str
    mqtt_tls: bool
    mqtt_ca_file: str | None
    proc_root: Path
    sys_root: Path
    fast_interval: int
    slow_interval: int
    hdd_interval: int
    volume_interval: int
    hdd_enabled: bool
    expected_hdd_count: int
    smart_snapshot_file: Path | None


def _bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _int(env: dict[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(env.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def load_config(env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ if env is None else env)
    nas_id = env.get("NAS_ID", "").strip().lower()
    if not ID_PATTERN.fullmatch(nas_id):
        raise ValueError("NAS_ID must be 1-40 lowercase letters, digits, _ or -")
    name = env.get("NAS_NAME", "UGREEN NAS").strip()
    if not name or len(name) > 80:
        raise ValueError("NAS_NAME must be 1-80 characters")
    host = env.get("MQTT_HOST", "").strip()
    if not host or any(c in host for c in "/# +"):
        raise ValueError("MQTT_HOST must be a host name or IP address")
    user = env.get("MQTT_USER", "").strip()
    if not user:
        raise ValueError("MQTT_USER is required")
    password_path = Path(env.get("MQTT_PASSWORD_FILE", "/run/secrets/mqtt_password"))
    password = password_path.read_text(encoding="utf-8").rstrip("\r\n")
    if not password:
        raise ValueError("MQTT password secret is empty")
    mqtt_protocol = env.get("MQTT_PROTOCOL", "3.1.1").strip()
    if mqtt_protocol not in {"3.1.1", "5"}:
        raise ValueError("MQTT_PROTOCOL must be 3.1.1 or 5")
    hdd_enabled = _bool(env.get("HDD_ENABLED", "false"), "HDD_ENABLED")
    expected = _int(env, "EXPECTED_HDD_COUNT", 0, 0, 24)
    if hdd_enabled and expected == 0:
        raise ValueError("EXPECTED_HDD_COUNT is required when HDD_ENABLED=true")
    mqtt_tls = _bool(env.get("MQTT_TLS", "false"), "MQTT_TLS")
    ca = env.get("MQTT_CA_FILE", "").strip() or None
    return Config(
        nas_id=nas_id,
        nas_name=name,
        mqtt_host=host,
        mqtt_port=_int(env, "MQTT_PORT", 8883 if mqtt_tls else 1883, 1, 65535),
        mqtt_user=user,
        mqtt_password=password,
        mqtt_protocol=mqtt_protocol,
        mqtt_tls=mqtt_tls,
        mqtt_ca_file=ca,
        proc_root=Path(env.get("PROC_ROOT", "/proc")),
        sys_root=Path(env.get("SYS_ROOT", "/host/sys")),
        fast_interval=_int(env, "FAST_INTERVAL_SECONDS", 60, 15, 59940),
        slow_interval=_int(env, "SLOW_INTERVAL_SECONDS", int(env.get("HDD_INTERVAL_SECONDS", "900")), 60, 59940),
        hdd_interval=_int(env, "HDD_INTERVAL_SECONDS", 900, 300, 86400),
        volume_interval=_int(env, "VOLUME_INTERVAL_SECONDS", 900, 60, 59940),
        hdd_enabled=hdd_enabled,
        expected_hdd_count=expected,
        smart_snapshot_file=Path(env["SMART_SNAPSHOT_FILE"]) if env.get("SMART_SNAPSHOT_FILE") else None,
    )
