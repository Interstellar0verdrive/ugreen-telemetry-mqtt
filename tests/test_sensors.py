import tempfile
import hashlib
import json
import runpy
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ugreen_telemetry.probe import inventory
from ugreen_telemetry.sensors import HostCollector, read_smart_snapshot, scan_disk_temperatures


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class SensorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.proc = root / "proc"
        self.sys = root / "sys"
        (self.sys / "block").mkdir(parents=True)
        (self.sys / "class" / "hwmon").mkdir(parents=True)

    def add_disk(self, disk: str, rotational: int, chip: str, temperature: str):
        device = self.sys / "devices" / "pci0000:00" / disk
        device.mkdir(parents=True)
        block = self.sys / "block" / disk
        block.mkdir()
        (block / "device").symlink_to(device)
        write(block / "queue" / "rotational", str(rotational))
        hwmon = self.sys / "class" / "hwmon" / f"hwmon{len(list((self.sys / 'class' / 'hwmon').iterdir()))}"
        hwmon.mkdir()
        (hwmon / "device").symlink_to(device)
        write(hwmon / "name", chip)
        write(hwmon / "temp1_input", temperature)
        return hwmon

    def test_cpu_ram_and_hdd_opt_in(self):
        write(self.proc / "stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        write(self.proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
        write(self.proc / "uptime", "7200.00 10.00\n")
        hwmon = self.add_disk("sda", 1, "drivetemp", "40000")
        collector = HostCollector(self.proc, self.sys)
        first = collector.collect_fast()
        self.assertNotIn("cpu_usage", first)
        self.assertEqual(first["memory_usage"].value, 75.0)
        self.assertNotIn("uptime", first)
        self.assertEqual(collector.collect_slow()["uptime"].value, 2.0)
        self.assertFalse(any(key.startswith("hdd_") for key in first))
        write(self.proc / "stat", "cpu  150 0 150 900 0 0 0 0 0 0\n")
        second = collector.collect_fast()
        self.assertEqual(second["cpu_usage"].value, 50.0)
        self.assertEqual(collector.collect_hdd(1).readings["hdd_max_temperature"].value, 40.0)
        write(hwmon / "temp1_input", "not-a-number")
        self.assertNotIn("hdd_max_temperature", collector.collect_hdd(1).readings)

    def test_hdd_max_requires_complete_coverage(self):
        self.add_disk("sda", 1, "drivetemp", "39000")
        self.add_disk("sdb", 1, "drivetemp", "45000")
        collector = HostCollector(self.proc, self.sys)
        scan = collector.collect_hdd(2)
        self.assertEqual(scan.hdd_count, 2)
        self.assertEqual(scan.covered_hdds, 2)
        self.assertEqual(scan.readings["hdd_max_temperature"].value, 45.0)
        self.assertNotIn("hdd_max_temperature", collector.collect_hdd(3).readings)

    def test_multiple_sensors_for_one_hdd_use_hottest_value(self):
        self.add_disk("sda", 1, "drivetemp", "45000")
        second = self.sys / "class" / "hwmon" / "hwmon1"
        second.mkdir()
        (second / "device").symlink_to(self.sys / "devices" / "pci0000:00" / "sda")
        write(second / "name", "drivetemp")
        write(second / "temp1_input", "40000")
        scan = HostCollector(self.proc, self.sys).collect_hdd(1)
        self.assertEqual(scan.readings["hdd_max_temperature"].value, 45.0)

    def test_nvme_and_ssd_are_automatic(self):
        self.add_disk("sda", 0, "drivetemp", "42000")
        self.add_disk("nvme0n1", 0, "nvme", "35000")
        scan = scan_disk_temperatures(self.sys, include_hdd=False)
        self.assertEqual(len(scan.readings), 2)
        self.assertTrue(any(key.startswith("ssd_") for key in scan.readings))
        self.assertTrue(any(key.startswith("nvme_") for key in scan.readings))

    def test_cpu_and_storage_temperatures_use_slow_collection(self):
        cpu = self.sys / "class" / "hwmon" / "hwmon0"
        cpu.mkdir()
        write(cpu / "name", "coretemp")
        write(cpu / "temp1_label", "Package id 0")
        write(cpu / "temp1_input", "51000")
        self.add_disk("nvme0n1", 0, "nvme", "35000")
        collector = HostCollector(self.proc, self.sys)
        fast = collector.collect_fast()
        slow = collector.collect_slow()
        self.assertNotIn("cpu_temperature", fast)
        self.assertFalse(any(key.startswith("nvme_") for key in fast))
        self.assertEqual(slow["cpu_temperature"].value, 51.0)
        self.assertTrue(any(key.startswith("nvme_") for key in slow))

    def test_probe_does_not_open_temperature_input(self):
        hwmon = self.add_disk("sda", 1, "drivetemp", "40000")
        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            if path.name.endswith("_input"):
                raise AssertionError("probe read a temperature input")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            rows = inventory(self.sys)
        self.assertEqual(rows[0]["disk"], "sda")
        self.assertEqual(rows[0]["temperature_inputs"], "temp1_input")

    def test_host_smart_snapshot_requires_fresh_complete_hdd_coverage(self):
        path = Path(self.temp.name) / "smart.json"
        data = {
            "version": 1,
            "sampled_at": int(time.time()),
            "hdd_count": 2,
            "readings": [
                {"key": "hdd_0123456789_temperature", "name": "HDD sda temperature", "temperature": 45},
                {"key": "hdd_abcdef0123_temperature", "name": "HDD sdb temperature", "temperature": 47},
            ],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        scan = read_smart_snapshot(path, 2, 1800)
        self.assertEqual(scan.readings["hdd_max_temperature"].value, 47.0)
        data["readings"].pop()
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotIn("hdd_max_temperature", read_smart_snapshot(path, 2, 1800).readings)
        data["sampled_at"] -= 3600
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(read_smart_snapshot(path, 2, 1800).readings, {})

    def test_host_smart_parser_prefers_attribute_194(self):
        helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "host-smart-snapshot.py"))
        sample = """190 Airflow_Temperature_Cel 0x0022 055 048 000 Old_age Always - 45 (Min/Max 30/49)
194 Temperature_Celsius 0x0022 045 052 000 Old_age Always - 46 (0 21 0 0 0)
"""
        self.assertEqual(helper["temperature_from_attributes"](sample), 46)

    def test_smart_disk_id_is_same_on_host_and_in_container(self):
        helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "host-smart-snapshot.py"))
        host_root = Path(self.temp.name) / "host-sys"
        container_root = Path(self.temp.name) / "container-sys"
        host_root.mkdir()
        container_root.mkdir()
        relative_device = Path("devices/pci0000:00/ata1/host0/target0:0:0/0:0:0:0")
        (host_root / relative_device).mkdir(parents=True)
        (container_root / relative_device).mkdir(parents=True)
        expected = hashlib.sha256(str(Path("/sys") / relative_device).encode()).hexdigest()[:10]
        self.assertEqual(helper["stable_device_id"]((host_root / relative_device).resolve(), host_root), expected)
        self.assertEqual(helper["stable_device_id"]((container_root / relative_device).resolve(), container_root), expected)

    def test_host_helper_queries_only_selected_disk_and_respects_no_wake(self):
        self.add_disk("sda", 1, "drivetemp", "45000")
        helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "host-smart-snapshot.py"))
        table = """4 Start_Stop_Count 0x0032 100 100 020 Old_age Always - 71
5 Reallocated_Sector_Ct 0x0033 100 100 010 Pre-fail Always - 0
193 Load_Cycle_Count 0x0032 100 100 000 Old_age Always - 310
194 Temperature_Celsius 0x0022 045 052 000 Old_age Always - 45 (0 21 0 0 0)
197 Current_Pending_Sector 0x0012 100 100 000 Old_age Always - 1
198 Offline_Uncorrectable 0x0010 100 100 000 Old_age Offline - 0
199 UDMA_CRC_Error_Count 0x003e 200 200 000 Old_age Always - 0
"""
        volume = Path(self.temp.name) / "volume1"
        volume.mkdir()
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, table, "")) as run, patch("os.path.ismount", return_value=True):
            data = helper["snapshot"](["/dev/sda"], Path("/usr/sbin/smartctl"), self.sys, False, {"data": volume})
        self.assertEqual(len(data["readings"]), 1)
        self.assertEqual(data["readings"][0]["temperature"], 45)
        self.assertEqual(data["readings"][0]["smart_counters"]["pending_sectors"], 1)
        self.assertEqual(data["readings"][0]["smart_counters"]["start_stop_count"], 71)
        self.assertEqual(data["readings"][0]["smart_counters"]["load_cycle_count"], 310)
        path = Path(self.temp.name) / "snapshot.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        parsed = read_smart_snapshot(path, 1, 1800).readings
        self.assertEqual(parsed["hdd_max_temperature"].value, 45)
        self.assertEqual(parsed["hdd_" + data["readings"][0]["key"].split("_")[1] + "_pending_sectors"].value, 1)
        start_stop = parsed["hdd_" + data["readings"][0]["key"].split("_")[1] + "_start_stop_count"]
        self.assertEqual(start_stop.value, 71)
        self.assertEqual(start_stop.state_class, "total_increasing")
        self.assertIn("volume_data_used_percent", parsed)
        self.assertIn("volume_data_available_gib", parsed)
        self.assertEqual(run.call_args.args[0], ["/usr/sbin/smartctl", "-d", "ata", "-n", "standby,0", "-A", "/dev/sda"])

        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, table, "")) as sat_run:
            sat_data = helper["snapshot"](["/dev/sda"], Path("/usr/sbin/smartctl"), self.sys, False,
                                          device_type="sat")
        self.assertEqual(sat_data["readings"][0]["temperature"], 45)
        self.assertEqual(sat_run.call_args.args[0],
                         ["/usr/sbin/smartctl", "-d", "sat", "-n", "standby,0", "-A", "/dev/sda"])

    def test_config_accepts_two_bay_and_custom_volume(self):
        helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "host-smart-snapshot.py"))
        targets = helper["validate_targets"](["/dev/sda", "/dev/sdb"], {"archive": "/volume2"})
        self.assertEqual(targets, {"archive": Path("/volume2")})
        with self.assertRaises(ValueError):
            helper["validate_targets"](["/dev/sda", "/dev/sda"], {})
        self.add_disk("sda", 1, "drivetemp", "40000")
        self.add_disk("sdb", 1, "drivetemp", "41000")
        installer = runpy.run_path(str(Path(__file__).resolve().parents[1] / "nas-install.py"))
        with patch("os.path.ismount", return_value=True):
            config, count = installer["inspect_targets"](["/dev/sda", "/dev/sdb"], ["archive=/volume2"], self.sys)
        self.assertEqual(config, {"devices": ["/dev/sda", "/dev/sdb"], "volumes": {"archive": "/volume2"}})
        self.assertEqual(count, 2)

    def test_guided_setup_discovers_two_bay_without_reading_smart(self):
        self.add_disk("sda", 1, "drivetemp", "40000")
        self.add_disk("sdb", 1, "drivetemp", "41000")
        installer = runpy.run_path(str(Path(__file__).resolve().parents[1] / "nas-install.py"))
        self.assertEqual([item[0] for item in installer["discover_disks"](self.sys)], ["/dev/sda", "/dev/sdb"])
        root = Path(self.temp.name) / "mounts"
        (root / "volume2").mkdir(parents=True)
        with patch("os.path.ismount", return_value=True):
            self.assertEqual(installer["discover_volumes"](root), [str(root / "volume2")])
        answers = ["1,2", "1", "", "", "", "192.0.2.10", "n", "", "", ""]
        with patch.dict(installer["guided_options"].__globals__, {
            "discover_disks": lambda: [("/dev/sda", "HDD"), ("/dev/sdb", "HDD")],
            "discover_volumes": lambda: ["/volume2"],
        }), patch("socket.gethostname", return_value="UGREEN2"), patch("builtins.input", side_effect=answers):
            options = installer["guided_options"]()
        self.assertEqual(options.disk, ["/dev/sda", "/dev/sdb"])
        self.assertEqual(options.volume, ["data1=/volume2"])
        self.assertEqual(options.nas_id, "ugreen2")
        self.assertEqual(options.mqtt_port, 1883)


if __name__ == "__main__":
    unittest.main()
