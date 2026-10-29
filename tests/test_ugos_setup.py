from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ugreen_telemetry import reader, web


class UgosSetupTests(unittest.TestCase):
    def test_volume_labels_keep_existing_home_assistant_identity(self):
        with patch.dict(web.os.environ, {"AVAILABLE_VOLUME_PATHS": "/volume1,/volume2"}):
            self.assertEqual(web.volume_inventory(), [
                {"path": "/host/volume1", "label": "data"},
                {"path": "/host/volume2", "label": "data2"},
            ])

    def test_inventory_and_target_validation_do_not_open_disks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "block" / "sda" / "queue").mkdir(parents=True)
            (root / "block" / "sda" / "queue" / "rotational").write_text("1\n")
            self.assertEqual(web.disk_inventory(root), [{"path": "/dev/sda", "type": "HDD"}])
            good = {"devices": ["/dev/sda"], "volumes": {"data1": "/host/volume1"}}
            self.assertEqual(reader.valid_targets(good, root), good)
            for bad in (
                {"devices": ["/dev/sdb"], "volumes": {}},
                {"devices": ["/dev/sda"], "volumes": {"data1": "/etc"}},
                {"devices": [{"path": "/dev/sda"}], "volumes": {}},
            ):
                with self.assertRaises(ValueError):
                    reader.valid_targets(bad, root)

    def test_password_is_kept_out_of_config_and_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            secret = root / "secrets"
            data.mkdir()
            secret.mkdir()
            raw = {
                "nas_id": "testnas", "nas_name": "Test NAS", "mqtt_host": "192.0.2.1",
                "mqtt_port": 1883, "mqtt_user": "telemetry", "mqtt_password": "private-test-password",
                "mqtt_protocol": "5", "mqtt_tls": False, "disks": ["/dev/sda"],
                "volumes": ["/host/volume1"], "sensor_groups": ["cpu", "hdd", "volume"],
            }
            with patch.object(web, "CONFIG", data / "config.json"), patch.object(web, "TARGETS", data / "targets.json"), \
                 patch.object(web, "PASSWORD", secret / "mqtt_password"), \
                 patch.object(web, "disk_inventory", return_value=[{"path": "/dev/sda", "type": "HDD"}]), \
                 patch.object(web, "volume_inventory", return_value=[{"path": "/host/volume1", "label": "data"}]):
                web.save_config(raw)
                self.assertNotIn("private-test-password", (data / "config.json").read_text())
                self.assertNotIn("private-test-password", (data / "targets.json").read_text())
                self.assertEqual(json.loads((data / "targets.json").read_text()),
                                 {"devices": ["/dev/sda"], "volumes": {"data": "/host/volume1"},
                                  "interval_seconds": 900, "volume_interval_seconds": 900})
                self.assertEqual((data / "targets.json").stat().st_mode & 0o777, 0o644)
                self.assertEqual((data / "config.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual((secret / "mqtt_password").stat().st_mode & 0o777, 0o600)

    def test_disabled_storage_groups_are_not_sampled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            secret = root / "secrets"
            data.mkdir()
            secret.mkdir()
            raw = {
                "nas_id": "testnas", "nas_name": "Test NAS", "mqtt_host": "192.0.2.1",
                "mqtt_port": 1883, "mqtt_user": "telemetry", "mqtt_password": "private-test-password",
                "mqtt_protocol": "5", "mqtt_tls": False,
                "disks": ["/dev/sda", "/dev/sdb"], "volumes": ["/host/volume1"],
                "sensor_groups": ["cpu", "nvme"],
            }
            disks = [{"path": "/dev/sda", "type": "HDD"}, {"path": "/dev/sdb", "type": "SATA SSD"}]
            with patch.object(web, "CONFIG", data / "config.json"), patch.object(web, "TARGETS", data / "targets.json"), \
                 patch.object(web, "PASSWORD", secret / "mqtt_password"), \
                 patch.object(web, "disk_inventory", return_value=disks), \
                 patch.object(web, "volume_inventory", return_value=[{"path": "/host/volume1", "label": "data"}]):
                web.save_config(raw)
                self.assertEqual(json.loads((data / "targets.json").read_text()),
                                 {"devices": ["/dev/sdb"], "volumes": {},
                                  "interval_seconds": 900, "volume_interval_seconds": 900})

    def test_runtime_targets_are_restored_from_persistent_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            runtime = root / "runtime"
            secrets = root / "secrets"
            for path in (data, runtime, secrets):
                path.mkdir()
            raw = {
                "nas_id": "testnas", "nas_name": "Test NAS", "mqtt_host": "192.0.2.1",
                "mqtt_port": 1883, "mqtt_user": "telemetry", "mqtt_password": "private-test-password",
                "mqtt_protocol": "5", "mqtt_tls": False, "disks": ["/dev/sda"],
                "volumes": ["/host/volume1"], "sensor_groups": ["hdd", "volume"],
            }
            with patch.object(web, "CONFIG", data / "config.json"), \
                 patch.object(web, "TARGETS", runtime / "targets.json"), \
                 patch.object(web, "PASSWORD", secrets / "mqtt_password"), \
                 patch.object(web, "disk_inventory", return_value=[{"path": "/dev/sda", "type": "HDD"}]), \
                 patch.object(web, "volume_inventory", return_value=[{"path": "/host/volume1", "label": "data"}]):
                web.save_config(raw)
                self.assertFalse((data / "targets.json").exists())
                (runtime / "targets.json").unlink()  # Simulate a cleared RAM volume after restart.
                web.restore_runtime_targets()
                self.assertEqual(json.loads((runtime / "targets.json").read_text()),
                                 {"devices": ["/dev/sda"], "volumes": {"data": "/host/volume1"},
                                  "interval_seconds": 900, "volume_interval_seconds": 900})
                self.assertEqual((runtime / "targets.json").stat().st_mode & 0o777, 0o644)

            with patch.object(web, "CONFIG", data / "config.json"), \
                 patch.object(web, "TARGETS", runtime / "targets.json"), \
                 patch.object(web, "disk_inventory", return_value=[]), \
                 patch.object(web, "volume_inventory", return_value=[]):
                web.restore_runtime_targets()
                self.assertEqual(json.loads((runtime / "targets.json").read_text()),
                                 {"devices": [], "volumes": {},
                                  "interval_seconds": 900, "volume_interval_seconds": 900})

    def test_empty_snapshot_replaces_old_storage_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "telemetry.json"
            path.write_text('{"readings":[{"temperature":42}]}')
            reader.write_empty_snapshot(path)
            data = json.loads(path.read_text())
            self.assertEqual(data["readings"], [])
            self.assertEqual(data["volumes"], [])
            self.assertEqual(data["hdd_count"], 0)

    def test_setup_token_rejects_missing_and_wrong_values(self):
        with tempfile.TemporaryDirectory() as folder:
            token = Path(folder) / "admin_token"
            token.write_text("test-token\n")
            handler = object.__new__(web.Handler)
            with patch.object(web, "TOKEN", token):
                handler.headers = {}
                self.assertFalse(handler._authorized())
                handler.headers = {"Authorization": "Bearer wrong-token"}
                self.assertFalse(handler._authorized())
                handler.headers = {"Authorization": "Bearer test-token"}
                self.assertTrue(handler._authorized())

    def test_saved_password_requires_setup_token_and_preserves_trailing_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            token = root / "admin_token"
            password = root / "mqtt_password"
            token.write_text("test-token\n")
            password.write_text("private-test-password  \n")
            handler = object.__new__(web.Handler)
            handler.path = "/api/password"
            handler._json = Mock()
            with patch.object(web, "TOKEN", token), patch.object(web, "PASSWORD", password):
                handler.headers = {"Authorization": "Bearer wrong-token"}
                handler.do_GET()
                handler._json.assert_called_with(401, {"error": "Invalid or missing setup token"})
                handler.headers = {"Authorization": "Bearer test-token"}
                handler.do_GET()
                handler._json.assert_called_with(200, {"password": "private-test-password  "})

    def test_publisher_restarts_on_config_save_signal(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            changed = threading.Event()
            supervisor = web.PublisherSupervisor()
            calls = 0

            def advance(_timeout):
                nonlocal calls
                calls += 1
                if calls == 1:
                    config.write_text("{}", encoding="utf-8")
                    changed.set()
                else:
                    supervisor.stop.set()

            with patch.object(web, "CONFIG", config), patch.object(web, "CONFIG_CHANGED", changed), \
                 patch.object(supervisor.stop, "wait", side_effect=advance), \
                 patch.object(supervisor, "_restart") as restart:
                supervisor.run()
                restart.assert_called_once()


if __name__ == "__main__":
    unittest.main()
