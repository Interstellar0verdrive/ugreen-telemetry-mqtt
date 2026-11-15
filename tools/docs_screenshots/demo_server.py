"""Serve the real setup wizard on localhost with example data, for documentation screenshots.

No disk, SMART or MQTT access: the inventory is fixed and the publisher never starts.
Run from the repository root:  PYTHONPATH=src python3 tools/docs_screenshots/demo_server.py
The example settings and a throwaway token are kept in tools/docs_screenshots/demo/.
"""
import json
import os
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA, SECRETS = HERE / "demo" / "data", HERE / "demo" / "secrets"
os.environ.update({
    "TELEMETRY_DATA_DIR": str(DATA), "TELEMETRY_SECRETS_DIR": str(SECRETS),
    "TARGETS_FILE": str(DATA / "targets.json"), "SETUP_BIND": "127.0.0.1",
    "SETUP_PORT": sys.argv[1] if len(sys.argv) > 1 else "8799",
})

from ugreen_telemetry import web  # noqa: E402

web.disk_inventory = lambda sys_root=None: [{"path": f"/dev/sd{x}", "type": "HDD"} for x in "abcd"]
web.volume_inventory = lambda: [{"path": "/host/volume1", "label": "data"}]


def idle(self):
    while not self.stop.is_set():
        time.sleep(1)


web.PublisherSupervisor.run = idle

for folder in (DATA, SECRETS):
    folder.mkdir(parents=True, exist_ok=True)
if "--fresh" in sys.argv:
    for path in (DATA / "config.json", SECRETS / "mqtt_password", DATA / "targets.json"):
        path.unlink(missing_ok=True)
elif not (DATA / "config.json").exists():
    (SECRETS / "mqtt_password").write_text("example-password\n")
    groups = sorted(web.SENSOR_GROUPS - {"nvme", "diagnostics"})
    config = {"nas_id": "dxp4800pro", "nas_name": "DXP4800 Pro", "mqtt_host": "192.0.2.10",
              "mqtt_port": 1883, "mqtt_user": "ugreen_telemetry", "mqtt_protocol": "5",
              "mqtt_tls": False, "disks": [f"/dev/sd{x}" for x in "abcd"],
              "volumes": ["/host/volume1"], "sensor_groups": groups,
              "intervals": dict(web.DEFAULT_INTERVALS)}
    (DATA / "config.json").write_text(json.dumps(config))
if not (SECRETS / "admin_token").exists():
    (SECRETS / "admin_token").write_text(secrets.token_urlsafe(32) + "\n")
web.main()
