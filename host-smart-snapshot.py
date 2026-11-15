#!/usr/bin/env python3
"""Read selected SATA disks and mounted-volume space on the NAS.

The network-isolated reader container runs this with raw disk access. The MQTT
publisher reads its output as an ordinary file and needs no block-device access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


DEVICE = re.compile(r"/dev/sd[a-z]+\Z")
VOLUME_LABEL = re.compile(r"[a-z][a-z0-9_]{0,19}\Z")
SMART_COUNTERS = {
    "4": ("Start_Stop_Count", "start_stop_count"),
    "5": ("Reallocated_Sector_Ct", "reallocated_sectors"),
    "193": ("Load_Cycle_Count", "load_cycle_count"),
    "197": ("Current_Pending_Sector", "pending_sectors"),
    "198": ("Offline_Uncorrectable", "uncorrectable_sectors"),
    "199": ("UDMA_CRC_Error_Count", "udma_crc_errors"),
}


def temperature_from_attributes(output: str) -> int | None:
    values: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 10 or fields[0] not in {"190", "194"}:
            continue
        try:
            value = int(fields[9])
        except ValueError:
            continue
        if 0 < value < 100:
            values[fields[0]] = value
    return values.get("194", values.get("190"))


def counters_from_attributes(output: str) -> dict[str, int]:
    counters: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 10 or fields[0] not in SMART_COUNTERS:
            continue
        expected_name, key = SMART_COUNTERS[fields[0]]
        if fields[1] != expected_name:
            continue
        try:
            value = int(fields[9])
        except ValueError:
            continue
        if 0 <= value <= 1_000_000_000:
            counters[key] = value
    return counters


def stable_device_id(physical_path: Path, sys_root: Path) -> str:
    """Use the host sysfs path so a bind mount does not change MQTT IDs."""
    relative_path = physical_path.relative_to(sys_root.resolve(strict=True))
    host_path = Path("/sys") / relative_path
    return hashlib.sha256(str(host_path).encode("utf-8")).hexdigest()[:10]


def inspect(device: str, smartctl: Path, sys_root: Path, allow_wake: bool, device_root: Path = Path("/dev"), device_type: str = "ata") -> tuple[str, dict | None]:
    name = Path(device).name
    rotational_file = sys_root / "block" / name / "queue" / "rotational"
    try:
        rotational = rotational_file.read_text(encoding="ascii").strip()
        physical_path = (sys_root / "block" / name / "device").resolve(strict=True)
    except OSError:
        return "unknown", None
    if rotational not in {"0", "1"}:
        return "unknown", None
    kind = "hdd" if rotational == "1" else "ssd"
    if device_type not in {"ata", "sat"}:
        raise ValueError("device type must be ata or sat")
    command = [str(smartctl), "-d", device_type]
    if not allow_wake:
        command += ["-n", "standby,0"]
    command += ["-A", str(device_root / name)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return kind, None
    # Bits 0 and 1 mean command-line/device-open failure. Other bits can report
    # SMART health warnings while still carrying a valid attribute table.
    if result.returncode < 0 or result.returncode & 0b11:
        return kind, None
    value = temperature_from_attributes(result.stdout)
    if value is None:
        return kind, None
    try:
        stable_id = stable_device_id(physical_path, sys_root)
    except (OSError, ValueError):
        return kind, None
    reading = {"key": f"{kind}_{stable_id}_temperature", "name": f"{kind.upper()} {name} temperature", "temperature": value}
    if kind == "hdd":
        reading["smart_counters"] = counters_from_attributes(result.stdout)
    return kind, reading


def volume_stats(label: str, path: Path) -> dict | None:
    try:
        # An unmounted volume path may still exist on the system filesystem.
        # Reject it rather than reporting the free space of the wrong device.
        if not path.is_dir() or not os.path.ismount(path):
            return None
        stats = os.statvfs(path)
    except OSError:
        return None
    total = stats.f_blocks * stats.f_frsize
    used = (stats.f_blocks - stats.f_bfree) * stats.f_frsize
    available = stats.f_bavail * stats.f_frsize
    if total <= 0 or used < 0 or available < 0 or used + available <= 0:
        return None
    return {
        "label": label,
        "used_percent": round(100 * used / (used + available), 1),
        "available_gib": round(available / (1024**3), 1),
    }


def snapshot(devices: list[str], smartctl: Path, sys_root: Path, allow_wake: bool, volumes: dict[str, Path] | None = None, device_root: Path = Path("/dev"), device_type: str = "ata") -> dict:
    readings: list[dict] = []
    hdd_count = 0
    for device in devices:
        kind, reading = inspect(device, smartctl, sys_root, allow_wake, device_root, device_type)
        if kind == "hdd":
            hdd_count += 1
        if reading is not None:
            readings.append(reading)
    volumes = volumes or {}
    volume_readings = [row for label, path in volumes.items() if (row := volume_stats(label, path)) is not None]
    return {
        "version": 2,
        "sampled_at": int(time.time()),
        "hdd_count": hdd_count,
        "readings": readings,
        "volume_count": len(volumes),
        "volumes": volume_readings,
    }


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".smart-", delete=False) as stream:
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


def validate_targets(devices: list[str], volumes: dict[str, str]) -> dict[str, Path]:
    if (not devices and not volumes) or any(not isinstance(item, str) or not DEVICE.fullmatch(item) for item in devices) or len(set(devices)) != len(devices):
        raise ValueError("devices must be unique /dev/sd* paths")
    if len(devices) > 24:
        raise ValueError("at most 24 devices are supported")
    if len(volumes) > 8:
        raise ValueError("at most 8 volumes are supported")
    checked: dict[str, Path] = {}
    for label, path in volumes.items():
        if not isinstance(label, str) or not VOLUME_LABEL.fullmatch(label) or not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("volumes require unique LABEL=/absolute/path entries")
        checked[label] = Path(path)
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("devices", nargs="*", help="explicit SATA device paths, e.g. /dev/sda /dev/sdb")
    parser.add_argument("--config", type=Path, help="JSON file containing device paths and labelled volume mounts")
    parser.add_argument("--smartctl", type=Path, default=Path("/usr/sbin/smartctl"))
    parser.add_argument("--sys-root", type=Path, default=Path("/sys"))
    parser.add_argument("--device-root", type=Path, default=Path("/dev"), help="mounted host device directory")
    parser.add_argument("--device-type", choices=("ata", "sat"), default="ata", help="smartctl access path; the reader container uses sat")
    parser.add_argument("--output", type=Path, help="write an atomic JSON snapshot instead of printing it")
    parser.add_argument("--allow-wake", action="store_true", help="allow SMART to wake disks from standby")
    parser.add_argument("--volume", action="append", default=[], metavar="LABEL=PATH", help="read filesystem space only, without listing its contents")
    args = parser.parse_args()
    try:
        if args.config:
            if args.devices or args.volume:
                parser.error("--config cannot be combined with devices or --volume")
            config = json.loads(args.config.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or set(config) != {"devices", "volumes"}:
                raise ValueError("config needs exactly devices and volumes")
            if not isinstance(config["devices"], list) or not isinstance(config["volumes"], dict):
                raise ValueError("config devices must be a list and volumes an object")
            devices = config["devices"]
            volumes = validate_targets(devices, config["volumes"])
        else:
            devices = args.devices
            raw_volumes: dict[str, str] = {}
            for item in args.volume:
                label, separator, path = item.partition("=")
                if not separator or label in raw_volumes:
                    raise ValueError("--volume requires unique LABEL=/absolute/path entries")
                raw_volumes[label] = path
            volumes = validate_targets(devices, raw_volumes)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    data = snapshot(devices, args.smartctl, args.sys_root, args.allow_wake, volumes, args.device_root, args.device_type)
    if args.output:
        write_atomic(args.output, data)
    else:
        print(json.dumps(data, separators=(",", ":")))
    return 0 if len(data["readings"]) == len(devices) and len(data["volumes"]) == len(volumes) else 1


if __name__ == "__main__":
    sys.exit(main())
