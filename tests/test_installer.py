"""Exercise a fresh guided install without touching host services or disks."""

import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


class InstallerTests(unittest.TestCase):
    def test_single_file_bundle_starts_installer_without_secret_files(self):
        project = Path(__file__).resolve().parents[1]
        builder = runpy.run_path(str(project / "tools" / "build_setup.py"))
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "setup.pyz"
            builder["build"](bundle)
            with ZipFile(bundle) as archive:
                names = archive.namelist()
            self.assertIn("__main__.py", names)
            self.assertIn("ugreen-telemetry-mqtt/nas-install.py", names)
            self.assertFalse(any("secrets/" in name or name.endswith("host.json") for name in names))
            result = subprocess.run([sys.executable, str(bundle), "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--mqtt-host", result.stdout)

    @staticmethod
    def arguments():
        return ["nas-install.py", "--nas-id", "nas2bay", "--nas-name", "Two Bay",
                "--mqtt-host", "192.0.2.10", "--mqtt-user", "telemetry",
                "--disk", "/dev/sda", "--disk", "/dev/sdb", "--volume", "archive=/volume2"]

    def test_fresh_two_bay_install_writes_private_config_and_starts_in_order(self):
        installer = runpy.run_path(str(Path(__file__).resolve().parents[1] / "nas-install.py"))
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / "app"
            units = Path(temp) / "units"
            units.mkdir()
            commands = []
            globals_ = installer["main"].__globals__
            with patch.dict(globals_, {
                "APP": app,
                "UNIT_DIR": units,
                "inspect_targets": lambda disks, volumes: (
                    {"devices": disks, "volumes": {"archive": "/volume2"}}, 2
                ),
                "run": lambda *command, cwd=None: commands.append((command, cwd)),
            }), patch("os.geteuid", return_value=0), patch("shutil.which", return_value="/usr/bin/docker"), \
                patch.object(Path, "is_file", return_value=True), \
                patch("builtins.input", return_value="yes"), \
                patch("getpass.getpass", return_value="test-only-password"), \
                patch("sys.argv", self.arguments()):
                self.assertEqual(installer["main"](), 0)

            self.assertEqual(json.loads((app / "host.json").read_text()), {
                "devices": ["/dev/sda", "/dev/sdb"], "volumes": {"archive": "/volume2"}
            })
            self.assertIn("EXPECTED_HDD_COUNT=2", (app / ".env").read_text())
            self.assertEqual((app / "secrets" / "mqtt_password.txt").read_text(), "test-only-password\n")
            self.assertEqual((app / ".env").stat().st_mode & 0o777, 0o600)
            self.assertEqual((app / "host.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((app / "secrets").stat().st_mode & 0o777, 0o700)
            self.assertEqual([command[:2] for command, _ in commands][-4:], [
                ("systemctl", "daemon-reload"), ("systemctl", "enable"),
                ("systemctl", "start"), ("docker", "compose"),
            ])
            self.assertTrue((units / "ugreen-telemetry-snapshot.timer").exists())
            self.assertTrue((units / "ugreen-telemetry-snapshot.service").exists())

    def test_failed_service_start_rolls_back_new_files(self):
        installer = runpy.run_path(str(Path(__file__).resolve().parents[1] / "nas-install.py"))
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / "app"
            units = Path(temp) / "units"
            units.mkdir()

            def fail_start(*command, cwd=None):
                if command[:2] == ("systemctl", "start"):
                    raise subprocess.CalledProcessError(1, command)

            with patch.dict(installer["main"].__globals__, {
                "APP": app, "UNIT_DIR": units,
                "inspect_targets": lambda disks, volumes: ({"devices": disks, "volumes": {}}, 2),
                "run": fail_start,
            }), patch("os.geteuid", return_value=0), patch("shutil.which", return_value="/usr/bin/docker"), \
                patch.object(Path, "is_file", return_value=True), \
                patch("builtins.input", return_value="yes"), \
                patch("getpass.getpass", return_value="test-only-password"), \
                patch("subprocess.run") as cleanup, patch("sys.argv", self.arguments()):
                with self.assertRaises(subprocess.CalledProcessError):
                    installer["main"]()
            self.assertFalse(app.exists())
            self.assertEqual(list(units.iterdir()), [])
            self.assertTrue(any(call.args[0][:2] == ("systemctl", "disable") for call in cleanup.call_args_list))


if __name__ == "__main__":
    unittest.main()
