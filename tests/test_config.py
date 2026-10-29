import tempfile
import unittest
from pathlib import Path

from ugreen_telemetry.config import load_config


class ConfigTests(unittest.TestCase):
    def test_hdd_needs_explicit_opt_in_and_count(self):
        with tempfile.TemporaryDirectory() as temp:
            secret = Path(temp) / "password"
            secret.write_text("example-only\n", encoding="utf-8")
            base = {
                "NAS_ID": "dxp4800pro",
                "MQTT_HOST": "192.0.2.10",
                "MQTT_USER": "telemetry",
                "MQTT_PASSWORD_FILE": str(secret),
            }
            cfg = load_config(base)
            self.assertFalse(cfg.hdd_enabled)
            self.assertEqual(cfg.mqtt_protocol, "3.1.1")
            self.assertEqual(load_config({**base, "MQTT_PROTOCOL": "5"}).mqtt_protocol, "5")
            with self.assertRaises(ValueError):
                load_config({**base, "MQTT_PROTOCOL": "6"})
            with self.assertRaises(ValueError):
                load_config({**base, "HDD_ENABLED": "true"})
            cfg = load_config({**base, "HDD_ENABLED": "true", "EXPECTED_HDD_COUNT": "4"})
            self.assertEqual(cfg.expected_hdd_count, 4)

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            load_config({"NAS_ID": "bad/topic"})


if __name__ == "__main__":
    unittest.main()
