"""Local setup UI and supervisor for the unprivileged MQTT publisher."""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import secrets
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlsplit


LOG = logging.getLogger(__name__)
DATA = Path(os.environ.get("TELEMETRY_DATA_DIR", "/data"))
SECRETS = Path(os.environ.get("TELEMETRY_SECRETS_DIR", "/secrets"))
ASSETS = Path(__file__).parent / "web_assets"
CONFIG = DATA / "config.json"
TARGETS = Path(os.environ.get("TARGETS_FILE", str(DATA / "targets.json")))
PASSWORD = SECRETS / "mqtt_password"
TOKEN = SECRETS / "admin_token"
CONFIG_CHANGED = threading.Event()
DISK = re.compile(r"/dev/sd[a-z]+\Z")
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}\Z")
HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}\Z")
SENSOR_GROUPS = {"cpu", "memory", "cpu_temperature", "hdd", "nvme", "uptime", "volume", "diagnostics"}
DEFAULT_GROUPS = sorted(SENSOR_GROUPS - {"diagnostics"})
DEFAULT_INTERVALS = {"cpu": 1, "memory": 1, "cpu_temperature": 15, "hdd": 15,
                     "nvme": 15, "uptime": 15, "volume": 15, "diagnostics": 15}
DISK_GROUPS = {"hdd", "nvme", "diagnostics"}
STORAGE_GROUPS = DISK_GROUPS | {"volume"}
SLOW_GROUPS = {"cpu_temperature", "uptime", "nvme"}

try:
    APP_VERSION = version("ugreen-telemetry-mqtt")
except PackageNotFoundError:
    APP_VERSION = "development"


def disk_inventory(sys_root: Path = Path("/host/sys")) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in sorted((sys_root / "block").glob("sd*")):
        if not DISK.fullmatch("/dev/" + entry.name):
            continue
        try:
            rotational = (entry / "queue" / "rotational").read_text(encoding="ascii").strip()
        except OSError:
            continue
        if rotational in {"0", "1"}:
            rows.append({"path": "/dev/" + entry.name, "type": "HDD" if rotational == "1" else "SATA SSD"})
    return rows


def volume_inventory() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for mount in os.environ.get("AVAILABLE_VOLUME_PATHS", "/volume1").split(","):
        mount = mount.strip()
        if re.fullmatch(r"/volume[1-9][0-9]*", mount):
            rows.append({"path": "/host" + mount, "label": volume_label(mount)})
    return rows


def volume_label(path: str) -> str:
    number = Path(path).name.removeprefix("volume")
    return "data" if number == "1" else "data" + number


def validate_config(raw: object) -> tuple[dict[str, object], str | None]:
    if not isinstance(raw, dict):
        raise ValueError("Configuration must be an object")
    nas_id = raw.get("nas_id")
    nas_name = raw.get("nas_name")
    broker = raw.get("mqtt_host")
    username = raw.get("mqtt_user")
    password = raw.get("mqtt_password")
    if not isinstance(nas_id, str) or not ID.fullmatch(nas_id):
        raise ValueError("NAS ID must use lowercase letters, numbers, _ or -")
    if not isinstance(nas_name, str) or not 1 <= len(nas_name.strip()) <= 80:
        raise ValueError("NAS name must be 1-80 characters")
    if not isinstance(broker, str) or not HOST.fullmatch(broker):
        raise ValueError("Invalid MQTT broker host")
    if not isinstance(username, str) or not 1 <= len(username.strip()) <= 128 or any(c.isspace() for c in username):
        raise ValueError("Invalid MQTT username")
    if password is not None and (not isinstance(password, str) or not 1 <= len(password) <= 512):
        raise ValueError("MQTT password must be 1-512 characters")
    if not PASSWORD.exists() and not password:
        raise ValueError("MQTT password is required on first setup")
    port = raw.get("mqtt_port", 1883)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid MQTT port")
    protocol = raw.get("mqtt_protocol", "5")
    if protocol not in {"5", "3.1.1"}:
        raise ValueError("Invalid MQTT protocol")
    tls = raw.get("mqtt_tls", False)
    if type(tls) is not bool:
        raise ValueError("Invalid TLS setting")
    disks = raw.get("disks", [])
    available_disks = {row["path"] for row in disk_inventory()}
    if not isinstance(disks, list) or len(disks) > 24 or any(
        not isinstance(item, str) or item not in available_disks for item in disks
    ) or len(disks) != len(set(disks)):
        raise ValueError("Choose disks from the discovered list")
    volumes = raw.get("volumes", [])
    available_volumes = {row["path"] for row in volume_inventory()}
    if not isinstance(volumes, list) or len(volumes) > 8 or any(
        not isinstance(item, str) or item not in available_volumes for item in volumes
    ) or len(volumes) != len(set(volumes)):
        raise ValueError("Choose volumes from the discovered list")
    groups = raw.get("sensor_groups", DEFAULT_GROUPS)
    if not isinstance(groups, list) or any(not isinstance(item, str) or item not in SENSOR_GROUPS for item in groups):
        raise ValueError("Invalid sensor selection")
    intervals = raw.get("intervals", DEFAULT_INTERVALS)
    if not isinstance(intervals, dict) or set(intervals) != SENSOR_GROUPS or any(
        type(minutes) is not int or not (5 if group in DISK_GROUPS else 1) <= minutes <= 999
        for group, minutes in intervals.items()
    ):
        raise ValueError("Reading intervals must be whole minutes within the allowed range")
    config = {
        "nas_id": nas_id, "nas_name": nas_name.strip(), "mqtt_host": broker,
        "mqtt_port": port, "mqtt_user": username, "mqtt_protocol": protocol, "mqtt_tls": tls,
        "disks": disks, "volumes": volumes, "sensor_groups": sorted(set(groups)),
        "intervals": intervals,
    }
    return config, password


def _atomic_text(path: Path, content: str, mode: int = 0o600) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp, mode)
    os.replace(temp, path)


def targets_for_config(config: dict[str, object]) -> dict[str, object]:
    groups = set(config["sensor_groups"])
    disk_types = {row["path"]: row["type"] for row in disk_inventory()}
    available_volumes = {row["path"] for row in volume_inventory()}
    return {
        "devices": [
            path for path in config["disks"]
            if path in disk_types and (
                (disk_types[path] == "HDD" and ("hdd" in groups or "diagnostics" in groups))
                or (disk_types[path] == "SATA SSD" and "nvme" in groups)
            )
        ],
        "volumes": {
            volume_label(path): path
            for path in config["volumes"] if "volume" in groups and path in available_volumes
        },
        "interval_seconds": min((config.get("intervals", DEFAULT_INTERVALS)[group] * 60
                                 for group in groups & DISK_GROUPS), default=900),
        "volume_interval_seconds": (config.get("intervals", DEFAULT_INTERVALS)["volume"] * 60
                                    if "volume" in groups and config["volumes"] else 900),
    }


def save_config(raw: object) -> dict[str, object]:
    config, password = validate_config(raw)
    available_disks = {row["path"] for row in disk_inventory()}
    if any(path not in available_disks for path in config["disks"]):
        raise ValueError("Selected disk disappeared; refresh the disk list")
    targets = targets_for_config(config)
    if password is not None:
        _atomic_text(PASSWORD, password + "\n")
    _atomic_text(TARGETS, json.dumps(targets, separators=(",", ":")) + "\n", 0o644)
    _atomic_text(CONFIG, json.dumps(config, separators=(",", ":")) + "\n")
    CONFIG_CHANGED.set()
    return config


def restore_runtime_targets() -> None:
    TARGETS.unlink(missing_ok=True)
    try:
        saved_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    targets = targets_for_config(saved_config)
    _atomic_text(TARGETS, json.dumps(targets, separators=(",", ":")) + "\n", 0o644)


class PublisherSupervisor:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def run(self) -> None:
        first_check = True
        while not self.stop.is_set():
            try:
                restart = CONFIG_CHANGED.is_set()
                if restart:
                    CONFIG_CHANGED.clear()
                if first_check:
                    first_check = False
                    restart = CONFIG.exists() or restart
                if self.process is not None and self.process.poll() is not None:
                    restart = True
                if restart:
                    with self.lock:
                        self._restart()
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                LOG.warning("Publisher configuration unavailable: %s", exc)
            self.stop.wait(3)
        with self.lock:
            self._terminate()

    def _terminate(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def _restart(self) -> None:
        self._terminate()
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        env = os.environ.copy()
        hdd_count = sum(row["path"] in config["disks"] and row["type"] == "HDD" for row in disk_inventory())
        env.update({
            "NAS_ID": config["nas_id"], "NAS_NAME": config["nas_name"],
            "MQTT_HOST": config["mqtt_host"], "MQTT_PORT": str(config["mqtt_port"]),
            "MQTT_USER": config["mqtt_user"], "MQTT_PROTOCOL": config["mqtt_protocol"],
            "MQTT_TLS": str(config["mqtt_tls"]).lower(), "MQTT_PASSWORD_FILE": str(PASSWORD),
            "SYS_ROOT": "/host/sys", "SMART_SNAPSHOT_FILE": "/snapshots/telemetry.json",
            "HDD_ENABLED": str(hdd_count > 0).lower(),
            "EXPECTED_HDD_COUNT": str(hdd_count),
            "SENSOR_GROUPS": ",".join(config["sensor_groups"]),
            "FAST_INTERVAL_SECONDS": str(min((config.get("intervals", DEFAULT_INTERVALS)[group] * 60
                                              for group in set(config["sensor_groups"]) & {"cpu", "memory"}), default=60)),
            "SLOW_INTERVAL_SECONDS": str(min((config.get("intervals", DEFAULT_INTERVALS)[group] * 60
                                              for group in set(config["sensor_groups"]) & SLOW_GROUPS), default=900)),
            "HDD_INTERVAL_SECONDS": str(min((config.get("intervals", DEFAULT_INTERVALS)[group] * 60
                                             for group in set(config["sensor_groups"]) & DISK_GROUPS), default=900)),
            "VOLUME_INTERVAL_SECONDS": str(config.get("intervals", DEFAULT_INTERVALS)["volume"] * 60),
            "GROUP_INTERVALS_JSON": json.dumps(config.get("intervals", DEFAULT_INTERVALS), separators=(",", ":")),
        })
        self.process = subprocess.Popen(["ugreen-telemetry"], env=env)
        LOG.info("MQTT publisher started")


class Handler(BaseHTTPRequestHandler):
    server_version = "UGREEN-Telemetry-Setup"

    def log_message(self, _format: str, *_args: object) -> None:
        pass  # URLs and credentials never enter access logs.

    def _send(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, value: object) -> None:
        self._send(code, json.dumps(value, separators=(",", ":")).encode("utf-8"), "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        supplied = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
        try:
            expected = TOKEN.read_text(encoding="ascii").strip()
        except OSError:
            return False
        return hmac.compare_digest(supplied, expected)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8"),
                  "/app-icon-dark.png": ("app-icon-dark.png", "image/png"),
                  "/app-icon-light.png": ("app-icon-light.png", "image/png")}
        if path in assets:
            name, kind = assets[path]
            data = (ASSETS / name).read_bytes()
            if name == "index.html":
                data = data.replace(b">Local preview</span>", b">v" + APP_VERSION.encode("ascii") + b"</span>")
            self._send(200, data, kind)
            return
        if path not in {"/api/status", "/api/password"}:
            self._json(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "Invalid or missing setup token"})
            return
        if path == "/api/password":
            try:
                password = PASSWORD.read_text(encoding="utf-8").removesuffix("\n")
            except FileNotFoundError:
                password = None
            self._json(200, {"password": password})
            return
        try:
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            config = None
        self._json(200, {"configured": config is not None, "config": config,
                         "saved_at": CONFIG.stat().st_mtime if config is not None else None,
                         "disks": disk_inventory(), "volumes": volume_inventory()})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/config":
            self._json(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "Unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384 or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                raise ValueError("Invalid request")
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            config = save_config(raw)
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {"saved": True, "config": config})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    DATA.mkdir(parents=True, exist_ok=True)
    DATA.chmod(0o755)
    SECRETS.mkdir(parents=True, exist_ok=True)
    SECRETS.chmod(0o700)
    if not TOKEN.exists():
        _atomic_text(TOKEN, secrets.token_urlsafe(32) + "\n")
    try:
        restore_runtime_targets()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        LOG.warning("Could not restore reader targets: %s", exc)
    LOG.warning("Setup URL: http://NAS-IP:%s/", os.environ.get("SETUP_PORT", "8765"))
    LOG.warning("Setup token (keep private): %s", TOKEN.read_text(encoding="ascii").strip())
    supervisor = PublisherSupervisor()
    thread = threading.Thread(target=supervisor.run, daemon=True)
    thread.start()
    server = ThreadingHTTPServer((os.environ.get("SETUP_BIND", "0.0.0.0"), int(os.environ.get("SETUP_PORT", "8765"))), Handler)
    server.daemon_threads = True
    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        supervisor.stop.set()
        thread.join(timeout=20)
        server.server_close()


if __name__ == "__main__":
    main()
