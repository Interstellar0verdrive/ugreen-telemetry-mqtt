#!/usr/bin/env python3
"""Install a fresh UGREEN telemetry instance from this unpacked directory.

Run as root only after checking the listed disks and mounted volumes. Existing
installations are deliberately left untouched; upgrade them separately.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path


APP = Path("/root/ugreen-telemetry-mqtt")
UNIT_DIR = Path("/etc/systemd/system")
UNIT = "ugreen-telemetry-snapshot"
DISK = re.compile(r"/dev/sd[a-z]+\Z")
LABEL = re.compile(r"[a-z][a-z0-9_]{0,19}\Z")
NAS_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}\Z")
SAFE_TEXT = re.compile(r"[\w .-]+\Z")
SAFE_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
SAFE_USER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]*\Z")


def discover_disks(sys_root: Path = Path("/sys")) -> list[tuple[str, str]]:
    """Read sysfs labels only; never open a disk or request SMART."""
    found: list[tuple[str, str]] = []
    for block in sorted((sys_root / "block").glob("sd*")):
        path = f"/dev/{block.name}"
        if not DISK.fullmatch(path):
            continue
        try:
            rotational = (block / "queue" / "rotational").read_text(encoding="ascii").strip()
            physical = (block / "device").resolve(strict=True)
        except OSError:
            continue
        if rotational not in {"0", "1"}:
            continue
        kind = "HDD" if rotational == "1" else "SSD SATA/USB (verify)"
        if any(part.startswith("usb") for part in physical.parts):
            kind += ", USB connection"
        found.append((path, kind))
    return found


def discover_volumes(root: Path = Path("/")) -> list[str]:
    """List conventional mounted data volumes without inspecting their files."""
    try:
        names = sorted(path.name for path in root.iterdir() if re.fullmatch(r"volume\d+", path.name))
    except OSError:
        return []
    return [str(root / name) for name in names if os.path.ismount(root / name)]


def choose_indices(prompt: str, size: int, allow_empty: bool = False) -> list[int]:
    raw = input(prompt).strip()
    if allow_empty and not raw:
        return []
    try:
        indices = [int(item.strip()) - 1 for item in raw.split(",")]
    except ValueError:
        raise ValueError("enter comma-separated numbers shown above") from None
    if not indices or len(set(indices)) != len(indices) or any(not 0 <= index < size for index in indices):
        raise ValueError("choose each listed number at most once")
    return indices


def guided_options() -> argparse.Namespace:
    print("UGREEN telemetry: guided setup. No disks are opened during discovery.")
    disks = discover_disks()
    if not disks:
        raise ValueError("no SATA disk candidates found; use explicit --disk options")
    print("\nDisks reported by Linux. Compare them with UGOS Storage before choosing:")
    for number, (path, kind) in enumerate(disks, 1):
        print(f"  {number}. {path} — {kind}")
    selected = choose_indices("Disk numbers to monitor (example: 1,2): ", len(disks))

    volumes = discover_volumes()
    print("\nMounted data volumes:")
    for number, path in enumerate(volumes, 1):
        print(f"  {number}. {path}")
    chosen_volumes = choose_indices("Volume numbers to monitor (Enter for none): ", len(volumes), allow_empty=True)
    volume_args = [f"data{number + 1}={volumes[index]}" for number, index in enumerate(chosen_volumes)]
    other_volume = input("Other mounted volume path (Enter for none): ").strip()
    if other_volume:
        volume_args.append(f"data{len(volume_args) + 1}={other_volume}")

    default_name = socket.gethostname().split(".")[0]
    default_id = re.sub(r"[^a-z0-9_-]", "-", default_name.lower()).strip("-_ ")[:40] or "ugreen-nas"
    nas_name = input(f"Name in Home Assistant [{default_name}]: ").strip() or default_name
    nas_id = input(f"Stable NAS identifier [{default_id}]: ").strip() or default_id
    print("Find the broker address in Home Assistant MQTT integration or your Mosquitto settings.")
    mqtt_host = input("MQTT broker IP or host: ").strip()
    tls_answer = input("Use MQTT TLS? [y/N]: ").strip().lower()
    if tls_answer not in {"", "n", "no", "y", "yes"}:
        raise ValueError("answer y or n for MQTT TLS")
    mqtt_tls = tls_answer in {"y", "yes"}
    default_port = 8883 if mqtt_tls else 1883
    mqtt_port = input(f"MQTT port [{default_port}]: ").strip() or str(default_port)
    mqtt_user = input("Dedicated MQTT username [ugreen_telemetry]: ").strip() or "ugreen_telemetry"
    mqtt_protocol = input("MQTT protocol [5] (5 or 3.1.1): ").strip() or "5"
    try:
        port = int(mqtt_port)
    except ValueError:
        raise ValueError("MQTT port must be a number") from None
    return argparse.Namespace(
        nas_id=nas_id, nas_name=nas_name, mqtt_host=mqtt_host, mqtt_port=port, mqtt_tls=mqtt_tls,
        mqtt_user=mqtt_user, mqtt_protocol=mqtt_protocol,
        disk=[disks[index][0] for index in selected], volume=volume_args,
    )


def inspect_targets(disks: list[str], volumes: list[str], sys_root: Path = Path("/sys")) -> tuple[dict, int]:
    if not disks or len(disks) > 24 or len(set(disks)) != len(disks):
        raise ValueError("specify 1-24 unique SATA disks")
    hdd_count = 0
    for disk in disks:
        if not DISK.fullmatch(disk):
            raise ValueError(f"invalid SATA disk path: {disk}")
        rotation = (sys_root / "block" / Path(disk).name / "queue" / "rotational").read_text(encoding="ascii").strip()
        if rotation not in {"0", "1"}:
            raise ValueError(f"unknown rotational status: {disk}")
        hdd_count += rotation == "1"
    if not 1 <= hdd_count <= 24:
        raise ValueError("at least one selected disk must be an HDD")
    if len(volumes) > 8:
        raise ValueError("at most eight volumes are supported")
    mounts: dict[str, str] = {}
    for item in volumes:
        label, separator, path = item.partition("=")
        if not separator or not LABEL.fullmatch(label) or label in mounts or not path.startswith("/"):
            raise ValueError("each volume must be a unique LABEL=/absolute/mount/path")
        if not os.path.ismount(path):
            raise ValueError(f"volume is not mounted: {path}")
        mounts[label] = path
    return {"devices": disks, "volumes": mounts}, hdd_count


def write_private(path: Path, data: str, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(data)
    path.chmod(mode)


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guided", action="store_true", help="ask only for the needed settings and show local disk/volume candidates")
    parser.add_argument("--nas-id", help="stable lowercase Home Assistant device identifier")
    parser.add_argument("--nas-name", help="display name in Home Assistant")
    parser.add_argument("--mqtt-host")
    parser.add_argument("--mqtt-port", type=int, help="default: 1883, or 8883 with --mqtt-tls")
    parser.add_argument("--mqtt-tls", action="store_true", help="verify TLS using system certificate authorities")
    parser.add_argument("--mqtt-user")
    parser.add_argument("--mqtt-protocol", choices=["3.1.1", "5"], default="3.1.1")
    parser.add_argument("--disk", action="append", help="confirmed /dev/sd* SATA disk; repeat per disk")
    parser.add_argument("--volume", action="append", default=[], help="LABEL=/mounted/path; repeat per volume")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("run as root with sudo")
    if APP.exists() or APP.is_symlink() or any(
        path.exists() or path.is_symlink()
        for path in (UNIT_DIR / f"{UNIT}.{suffix}" for suffix in ("service", "timer"))
    ):
        parser.error("an installation already exists; this installer never overwrites it")
    if args.guided or len(sys.argv) == 1:
        if any((args.nas_id, args.nas_name, args.mqtt_host, args.mqtt_user, args.disk, args.volume, args.mqtt_tls, args.mqtt_port)) or args.mqtt_protocol != "3.1.1":
            parser.error("--guided cannot be combined with explicit settings")
        try:
            args = guided_options()
        except ValueError as exc:
            parser.error(str(exc))
    elif not all((args.nas_id, args.nas_name, args.mqtt_host, args.mqtt_user, args.disk)):
        parser.error("explicit setup needs --nas-id, --nas-name, --mqtt-host, --mqtt-user and --disk")
    if args.mqtt_port is None:
        args.mqtt_port = 8883 if args.mqtt_tls else 1883
    if args.mqtt_protocol not in {"3.1.1", "5"}:
        parser.error("MQTT protocol must be 3.1.1 or 5")
    if not NAS_ID.fullmatch(args.nas_id) or not SAFE_TEXT.fullmatch(args.nas_name) or len(args.nas_name) > 80:
        parser.error("invalid NAS identifier or display name")
    if not SAFE_HOST.fullmatch(args.mqtt_host) or not 1 <= args.mqtt_port <= 65535:
        parser.error("invalid MQTT host or port")
    if not SAFE_USER.fullmatch(args.mqtt_user):
        parser.error("invalid MQTT user")
    for executable in ("/usr/bin/python3", "/usr/sbin/smartctl", "/usr/bin/systemctl"):
        if not Path(executable).is_file():
            parser.error(f"required executable is missing: {executable}")
    if not shutil.which("docker"):
        parser.error("Docker is required")
    try:
        targets, hdd_count = inspect_targets(args.disk, args.volume)
        run("docker", "compose", "version")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print("Disks:", ", ".join(args.disk), f"({hdd_count} HDD)")
    print("Volumes:", targets["volumes"] or "none")
    print("NAS:", args.nas_id, args.nas_name)
    print("MQTT:", args.mqtt_host, args.mqtt_port, args.mqtt_user)
    if input("Install with these targets? [yes/NO] ").strip().lower() != "yes":
        return 1
    password = getpass.getpass("Password for the dedicated MQTT user: ")
    if not password:
        parser.error("MQTT password cannot be empty")

    source = Path(__file__).resolve().parent
    installed_units: list[Path] = []
    compose_started = False
    try:
        shutil.copytree(source, APP, ignore=shutil.ignore_patterns(".git", ".github", "tests", "tools", "__pycache__", "*.pyc", "secrets", ".env"))
        APP.chmod(0o755)
        for copied in APP.rglob("*"):
            copied.chmod(0o755 if copied.is_dir() else 0o644)
        snapshots = APP / "snapshots"
        snapshots.mkdir(mode=0o755)
        secrets = APP / "secrets"
        secrets.mkdir(mode=0o700)
        write_private(APP / "host.json", json.dumps(targets, separators=(",", ":")) + "\n", 0o600)
        write_private(secrets / "mqtt_password.txt", password + "\n", 0o644)
        env = (
            f"NAS_ID={args.nas_id}\nNAS_NAME={args.nas_name}\nMQTT_HOST={args.mqtt_host}\n"
            f"MQTT_PORT={args.mqtt_port}\nMQTT_USER={args.mqtt_user}\nMQTT_PROTOCOL={args.mqtt_protocol}\n"
            f"MQTT_TLS={'true' if args.mqtt_tls else 'false'}\nFAST_INTERVAL_SECONDS=60\nHDD_ENABLED=true\n"
            f"EXPECTED_HDD_COUNT={hdd_count}\nHDD_INTERVAL_SECONDS=900\nSMART_SNAPSHOT_DIR={snapshots}\n"
        )
        write_private(APP / ".env", env, 0o600)
        run("docker", "compose", "-f", "compose.yaml", "-f", "compose.smart.yaml", "config", "--quiet", cwd=APP)
        run("docker", "compose", "-f", "compose.yaml", "-f", "compose.smart.yaml", "build", cwd=APP)
        for suffix in ("service", "timer"):
            destination = UNIT_DIR / f"{UNIT}.{suffix}"
            shutil.copy2(APP / "systemd" / destination.name, destination)
            installed_units.append(destination)
        run("systemctl", "daemon-reload")
        run("systemctl", "enable", "--now", f"{UNIT}.timer")
        run("systemctl", "start", f"{UNIT}.service")
        compose_started = True
        run("docker", "compose", "-f", "compose.yaml", "-f", "compose.smart.yaml", "up", "-d", cwd=APP)
    except (OSError, ValueError, shutil.Error, subprocess.CalledProcessError, KeyboardInterrupt):
        # Preflight guarantees these paths did not exist before this attempt.
        # Undo partial service/container creation so a corrected retry can run.
        if compose_started:
            subprocess.run(("docker", "compose", "-f", "compose.yaml", "-f", "compose.smart.yaml", "down"), cwd=APP, check=False)
        if installed_units:
            subprocess.run(("systemctl", "disable", "--now", f"{UNIT}.timer"), check=False)
            for path in installed_units:
                path.unlink(missing_ok=True)
            subprocess.run(("systemctl", "daemon-reload"), check=False)
        shutil.rmtree(APP, ignore_errors=True)
        print("Install failed; created files and services were rolled back where possible.", file=sys.stderr)
        raise
    print("Installed. Check Home Assistant MQTT Discovery after the first publication.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
