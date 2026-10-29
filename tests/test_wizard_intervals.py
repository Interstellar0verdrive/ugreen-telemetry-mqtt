from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ugreen_telemetry import main, reader, sensors, web


class WizardIntervalTests(unittest.TestCase):
    def test_disk_and_volume_intervals_remain_independent(self):
        intervals = dict(web.DEFAULT_INTERVALS, hdd=30, nvme=30, diagnostics=30, volume=1)
        config = {"disks": ["/dev/sda"], "volumes": ["/host/volume1"],
                  "sensor_groups": ["hdd", "volume"], "intervals": intervals}
        with patch.object(web, "disk_inventory", return_value=[{"path": "/dev/sda", "type": "HDD"}]), \
             patch.object(web, "volume_inventory", return_value=[{"path": "/host/volume1", "label": "data"}]):
            targets = web.targets_for_config(config)
        self.assertEqual(targets["interval_seconds"], 1800)
        self.assertEqual(targets["volume_interval_seconds"], 60)
        self.assertEqual(main.group_intervals(json.dumps(intervals), 60, 900, 1800, 60)["volume"], 60)
        self.assertEqual(main.group_intervals(json.dumps(intervals), 60, 900, 1800, 60)["hdd"], 1800)

    def test_volume_only_sample_does_not_pass_devices_to_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            targets = {"devices": ["/dev/sda"], "volumes": {"data": "/host/volume1"}}
            def run(command, **_kwargs):
                passed = json.loads((root / "validated-targets.json").read_text())
                self.assertEqual(passed, {"devices": [], "volumes": {"data": "/host/volume1"}})
                self.assertNotIn("/dev/sda", command)
                (root / "part-snapshot.json").write_text(json.dumps({
                    "sampled_at": int(time.time()), "hdd_count": 0, "readings": [],
                    "volume_count": 1, "volumes": [{"label": "data", "used_percent": 50, "available_gib": 100}]
                }))
                return type("Result", (), {"returncode": 0})()
            with patch.object(reader.subprocess, "run", side_effect=run):
                sample = reader._sample_part(targets, devices=False, volumes=True, workdir=root)
            self.assertEqual(sample["volume_count"], 1)

    def test_new_snapshot_omits_stale_disk_but_keeps_fresh_volume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            now = int(time.time())
            snapshot = {"version": 3, "sampled_at": now, "disk_sampled_at": now - 2000,
                        "volume_sampled_at": now, "hdd_count": 1,
                        "readings": [{"key": "hdd_0123456789_temperature", "name": "HDD sda temperature", "temperature": 42}],
                        "volume_count": 1, "volumes": [{"label": "data", "used_percent": 50, "available_gib": 100}]}
            path.write_text(json.dumps(snapshot))
            scan = sensors.read_smart_snapshot(path, 1, 1800, 120)
            self.assertNotIn("hdd_0123456789_temperature", scan.readings)
            self.assertIn("volume_data_used_percent", scan.readings)
            snapshot["disk_sampled_at"] = now
            snapshot["volume_sampled_at"] = now - 2000
            path.write_text(json.dumps(snapshot))
            scan = sensors.read_smart_snapshot(path, 1, 1800, 120)
            self.assertIn("hdd_0123456789_temperature", scan.readings)
            self.assertNotIn("volume_data_used_percent", scan.readings)

    def test_invalid_interval_rejected_before_config_is_saved(self):
        raw = {"nas_id": "testnas", "nas_name": "Test", "mqtt_host": "192.0.2.1",
               "mqtt_user": "telemetry", "mqtt_password": "dummy", "disks": [], "volumes": [],
               "intervals": dict(web.DEFAULT_INTERVALS, hdd=1)}
        with patch.object(web, "disk_inventory", return_value=[]), patch.object(web, "volume_inventory", return_value=[]):
            with self.assertRaisesRegex(ValueError, "intervals"):
                web.validate_config(raw)

    def test_volume_and_nvme_readings_use_their_actual_sources(self):
        volume = sensors.Reading("volume_data_used_percent", "Volume data used", 50, "%")
        nvme = sensors.Reading("nvme_test_temperature", "NVMe temperature", 35, "°C")
        selected = main._group_readings("volume", {}, {}, {volume.key: volume},
                                        100, 0, 0, 100, 60, 900, 900, 60)
        self.assertEqual(selected, {volume.key: volume})
        selected = main._group_readings("nvme", {}, {nvme.key: nvme}, {},
                                        100, 0, 100, 0, 60, 300, 900, 60)
        self.assertEqual(selected, {nvme.key: nvme})


if __name__ == "__main__":
    unittest.main()
