from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path


DISK_NAME = re.compile(r"(?:sd[a-z]+|nvme\d+n\d+)\Z")
CONTROLLER_NAME = re.compile(r"nvme\d+\Z")


@dataclass(frozen=True)
class Reading:
    key: str
    name: str
    value: float
    unit: str
    device_class: str | None = None
    state_class: str | None = "measurement"
    entity_category: str | None = None


@dataclass(frozen=True)
class DiskScan:
    readings: dict[str, Reading]
    hdd_count: int
    covered_hdds: int


def _read(path: Path) -> str | None:
    try:
        # The caller only supplies fixed proc/sysfs attributes, never a user path.
        return path.read_text(encoding="utf-8", errors="replace")[:4096].strip()
    except (OSError, ValueError):
        return None


def _number(path: Path) -> int | None:
    raw = _read(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _temperature(path: Path, maximum: float = 125.0) -> float | None:
    raw = _number(path)
    if raw is None:
        return None
    value = raw / 1000.0
    return round(value, 2) if 0.0 < value < maximum else None


def _cpu_ticks(proc_root: Path) -> tuple[int, int] | None:
    raw = _read(proc_root / "stat")
    if not raw:
        return None
    first = raw.splitlines()[0].split()
    if len(first) < 6 or first[0] != "cpu":
        return None
    try:
        ticks = [int(value) for value in first[1:]]
    except ValueError:
        return None
    return sum(ticks), ticks[3] + ticks[4]


class HostCollector:
    def __init__(self, proc_root: Path, sys_root: Path):
        self.proc_root = proc_root
        self.sys_root = sys_root
        self.previous_cpu: tuple[int, int] | None = None

    def collect_fast(self) -> dict[str, Reading]:
        readings: dict[str, Reading] = {}
        ticks = _cpu_ticks(self.proc_root)
        if ticks is not None:
            if self.previous_cpu is not None:
                total = ticks[0] - self.previous_cpu[0]
                idle = ticks[1] - self.previous_cpu[1]
                if total > 0 and 0 <= idle <= total:
                    readings["cpu_usage"] = Reading(
                        "cpu_usage", "CPU usage", round(100 * (total - idle) / total, 1), "%"
                    )
            self.previous_cpu = ticks

        raw = _read(self.proc_root / "meminfo")
        if raw:
            values: dict[str, int] = {}
            for line in raw.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] in {"MemTotal:", "MemAvailable:"}:
                    try:
                        values[parts[0]] = int(parts[1])
                    except ValueError:
                        pass
            total = values.get("MemTotal:", 0)
            available = values.get("MemAvailable:", -1)
            if total > 0 and 0 <= available <= total:
                readings["memory_usage"] = Reading(
                    "memory_usage", "Memory usage", round(100 * (total - available) / total, 1), "%"
                )

        return readings

    def collect_slow(self) -> dict[str, Reading]:
        readings: dict[str, Reading] = {}
        uptime = _read(self.proc_root / "uptime")
        if uptime:
            try:
                seconds = float(uptime.split()[0])
            except (ValueError, IndexError):
                seconds = 0
            if 0 < seconds < 1e10:
                readings["uptime"] = Reading("uptime", "Uptime", round(seconds / 3600, 2), "h", "duration")

        package_temps: list[float] = []
        for hwmon in sorted((self.sys_root / "class" / "hwmon").glob("hwmon*")):
            chip = _read(hwmon / "name")
            if chip not in {"coretemp", "k10temp", "cpu_thermal"}:
                continue
            for input_file in sorted(hwmon.glob("temp*_input")):
                label = _read(input_file.with_name(input_file.name.replace("_input", "_label"))) or ""
                if chip == "coretemp" and not label.startswith("Package id"):
                    continue
                value = _temperature(input_file)
                if value is not None:
                    package_temps.append(value)
        if package_temps:
            readings["cpu_temperature"] = Reading(
                "cpu_temperature", "CPU temperature", max(package_temps), "°C", "temperature"
            )

        readings.update(scan_disk_temperatures(self.sys_root, include_hdd=False).readings)
        return readings

    def collect_hdd(self, expected_hdd_count: int) -> DiskScan:
        scan = scan_disk_temperatures(self.sys_root, include_hdd=True)
        readings = {key: value for key, value in scan.readings.items() if key.startswith("hdd_")}
        if scan.hdd_count == expected_hdd_count and scan.covered_hdds == expected_hdd_count:
            temperatures = [reading.value for reading in readings.values()]
            if temperatures:
                readings["hdd_max_temperature"] = Reading(
                    "hdd_max_temperature", "HDD maximum temperature", max(temperatures), "°C", "temperature"
                )
        return DiskScan(readings, scan.hdd_count, scan.covered_hdds)


def read_smart_snapshot(path: Path, expected_hdd_count: int, max_age: int,
                        volume_max_age: int | None = None) -> DiskScan:
    """Accept only recent allowlisted output from the host SMART helper."""
    empty = DiskScan({}, 0, 0)
    try:
        if path.stat().st_size > 65536:
            return empty
        data = json.loads(path.read_text(encoding="utf-8"))
        sampled_at = data["sampled_at"]
        hdd_count = data["hdd_count"]
        rows = data["readings"]
        version = data["version"]
        if version not in {1, 2, 3} or type(sampled_at) is not int or type(hdd_count) is not int or type(rows) is not list:
            return empty
        allowed_age = max(max_age, volume_max_age or max_age)
        if not 0 <= time.time() - sampled_at <= allowed_age or not 0 <= hdd_count <= 24 or len(rows) > 24:
            return empty
        volumes = data["volumes"] if version >= 2 else []
        volume_count = data["volume_count"] if version >= 2 else 0
        if type(volumes) is not list or type(volume_count) is not int or not 0 <= volume_count <= 8 or len(volumes) > volume_count:
            return empty
        if version == 3:
            disk_at, volume_at = data["disk_sampled_at"], data["volume_sampled_at"]
            if type(disk_at) is not int or type(volume_at) is not int:
                return empty
            if not 0 <= time.time() - disk_at <= max_age:
                rows, hdd_count = [], 0
            if not 0 <= time.time() - volume_at <= (volume_max_age or max_age):
                volumes, volume_count = [], 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return empty
    readings: dict[str, Reading] = {}
    covered = 0
    for row in rows:
        if not isinstance(row, dict):
            return empty
        key, name, value = row.get("key"), row.get("name"), row.get("temperature")
        if not isinstance(key, str) or not re.fullmatch(r"(?:hdd|ssd)_[0-9a-f]{10}_temperature", key):
            return empty
        if not isinstance(name, str) or not re.fullmatch(r"(?:HDD|SSD) sd[a-z]+ temperature", name):
            return empty
        if type(value) not in {int, float} or not 0 < value < 100 or key in readings:
            return empty
        readings[key] = Reading(key, name, float(value), "°C", "temperature")
        if key.startswith("hdd_"):
            covered += 1
            counters = row.get("smart_counters", {})
            if not isinstance(counters, dict):
                return empty
            labels = {
                "start_stop_count": ("start/stop count", "cycles"),
                "load_cycle_count": ("load cycle count", "cycles"),
                "reallocated_sectors": ("reallocated sectors", "sectors"),
                "pending_sectors": ("pending sectors", "sectors"),
                "uncorrectable_sectors": ("uncorrectable sectors", "sectors"),
                "udma_crc_errors": ("UDMA CRC errors", "errors"),
            }
            if any(item not in labels or type(number) is not int or not 0 <= number <= 1_000_000_000 for item, number in counters.items()):
                return empty
            for item, number in counters.items():
                sensor_key = key.removesuffix("temperature") + item
                label, unit = labels[item]
                readings[sensor_key] = Reading(
                    sensor_key,
                    name.removesuffix("temperature") + label,
                    float(number),
                    unit,
                    state_class="total_increasing" if item in {"start_stop_count", "load_cycle_count"} else "measurement",
                    entity_category="diagnostic",
                )
    if covered > hdd_count:
        return empty
    if hdd_count == expected_hdd_count and covered == expected_hdd_count and covered > 0:
        readings["hdd_max_temperature"] = Reading(
            "hdd_max_temperature", "HDD maximum temperature",
            max(reading.value for key, reading in readings.items() if key.startswith("hdd_") and key.endswith("_temperature")),
            "°C", "temperature",
        )
    seen_volumes: set[str] = set()
    for row in volumes:
        if not isinstance(row, dict):
            return empty
        label, used, available = row.get("label"), row.get("used_percent"), row.get("available_gib")
        if not isinstance(label, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,19}", label) or label in seen_volumes:
            return empty
        if type(used) not in {int, float} or not 0 <= used <= 100:
            return empty
        if type(available) not in {int, float} or not 0 <= available <= 1_000_000_000:
            return empty
        seen_volumes.add(label)
        readings[f"volume_{label}_used_percent"] = Reading(
            f"volume_{label}_used_percent", f"Volume {label} used", float(used), "%"
        )
        readings[f"volume_{label}_available_gib"] = Reading(
            f"volume_{label}_available_gib", f"Volume {label} available", float(available), "GiB"
        )
    return DiskScan(readings, hdd_count, covered)


def _disks(sys_root: Path) -> dict[str, tuple[Path, int]]:
    result: dict[str, tuple[Path, int]] = {}
    for entry in sorted((sys_root / "block").iterdir()):
        if not DISK_NAME.fullmatch(entry.name):
            continue
        rotational = _number(entry / "queue" / "rotational")
        if rotational not in {0, 1}:
            continue
        try:
            device = (entry / "device").resolve(strict=True)
        except OSError:
            continue
        result[entry.name] = device, rotational
    return result


def _associated_disk(hwmon: Path, disks: dict[str, tuple[Path, int]]) -> str | None:
    try:
        target = (hwmon / "device").resolve(strict=True)
    except OSError:
        return None
    parts = set(target.parts)
    direct = [name for name in disks if name in parts]
    if len(direct) == 1:
        return direct[0]
    exact = [name for name, (device, _) in disks.items() if device == target]
    if len(exact) == 1:
        return exact[0]
    controllers = {part for part in parts if CONTROLLER_NAME.fullmatch(part)}
    if len(controllers) == 1:
        controller = next(iter(controllers))
        namespaces = [name for name in disks if name.startswith(controller + "n")]
        if len(namespaces) == 1:
            return namespaces[0]
    return None


def scan_disk_temperatures(sys_root: Path, include_hdd: bool) -> DiskScan:
    try:
        disks = _disks(sys_root)
    except OSError:
        return DiskScan({}, 0, 0)
    hdds = {name for name, (_, rotational) in disks.items() if rotational == 1}
    seen_hdds: set[str] = set()
    readings: dict[str, Reading] = {}
    for hwmon in sorted((sys_root / "class" / "hwmon").glob("hwmon*")):
        chip = _read(hwmon / "name")
        if chip not in {"drivetemp", "nvme"}:
            continue
        disk = _associated_disk(hwmon, disks)
        if disk is None:
            continue
        device, rotational = disks[disk]
        if rotational and not include_hdd:
            continue
        value = _temperature(hwmon / "temp1_input", maximum=100.0)
        if value is None:
            continue
        kind = "hdd" if rotational else ("nvme" if disk.startswith("nvme") else "ssd")
        # Identity follows the bus location, without publishing path or serial.
        stable_id = hashlib.sha256(str(device).encode("utf-8")).hexdigest()[:10]
        key = f"{kind}_{stable_id}_temperature"
        if key not in readings or value > readings[key].value:
            readings[key] = Reading(key, f"{kind.upper()} {disk} temperature", value, "°C", "temperature")
        if rotational:
            seen_hdds.add(disk)
    return DiskScan(readings, len(hdds), len(seen_hdds))
