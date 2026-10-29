"""Read-only inventory: never opens a temperature input or block device."""

from __future__ import annotations

from pathlib import Path

from .sensors import _associated_disk, _disks, _read


def inventory(sys_root: Path) -> list[dict[str, str]]:
    disks = _disks(sys_root)
    rows: list[dict[str, str]] = []
    for hwmon in sorted((sys_root / "class" / "hwmon").glob("hwmon*")):
        chip = _read(hwmon / "name") or "unknown"
        disk = _associated_disk(hwmon, disks)
        rows.append({
            "sensor": hwmon.name,
            "chip": chip,
            "disk": disk or "unmatched",
            "kind": "HDD" if disk and disks[disk][1] else "SSD/NVMe" if disk else "host/unknown",
            "temperature_inputs": ",".join(sorted(path.name for path in hwmon.glob("temp*_input"))) or "none",
        })
    return rows


def print_inventory(sys_root: Path) -> None:
    rows = inventory(sys_root)
    print("sensor\tchip\tdisk\tkind\ttemperature_inputs")
    for row in rows:
        print("\t".join(row[key] for key in ("sensor", "chip", "disk", "kind", "temperature_inputs")))
