import json
import unittest

from ugreen_telemetry.mqtt import TelemetryPublisher
from ugreen_telemetry.sensors import Reading


class Result:
    rc = 0

    def wait_for_publish(self, timeout=10.0):
        return True

    def is_published(self):
        return True


class FakeClient:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos, retain):
        self.sent.append((topic, payload, qos, retain))
        return Result()


class MQTTTests(unittest.TestCase):
    def test_discovery_state_and_availability_are_publication_only(self):
        client = FakeClient()
        publisher = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session1")
        publisher.publish_batch("fast", {
            "memory_usage": Reading("memory_usage", "Memory usage", 32.5, "%")
        })
        publisher.online()
        topics = [item[0] for item in client.sent]
        discovery_topic = "homeassistant/sensor/ugreen_telemetry_dxp4800pro/memory_usage/config"
        self.assertIn(discovery_topic, topics)
        config = json.loads(next(payload for topic, payload, _, _ in client.sent if topic == discovery_topic))
        self.assertEqual(config["state_topic"], "ugreen_telemetry/dxp4800pro/sensor/memory_usage/state")
        self.assertNotIn("enabled_by_default", config)
        self.assertNotIn("command_topic", config)
        self.assertNotIn("serial", json.dumps(config))
        self.assertTrue(all(qos == 1 and retain for _, _, qos, retain in client.sent))
        publisher.publish_batch("fast", {})
        self.assertIn(
            ("ugreen_telemetry/dxp4800pro/sensor/memory_usage/availability", "offline", 1, True),
            client.sent,
        )

    def test_reconnect_republishes_discovery(self):
        client = FakeClient()
        publisher = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session1")
        reading = Reading("cpu_usage", "CPU usage", 15.0, "%")
        publisher.publish_batch("fast", {reading.key: reading})
        publisher.reconnect()
        publisher.publish_batch("fast", {reading.key: reading})
        topics = [item[0] for item in client.sent]
        self.assertEqual(
            topics.count("homeassistant/sensor/ugreen_telemetry_dxp4800pro/cpu_usage/config"), 2
        )

    def test_smart_counter_is_discovery_diagnostic(self):
        client = FakeClient()
        publisher = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session1")
        reading = Reading("hdd_0123456789_pending_sectors", "HDD sda pending sectors", 1, "sectors", entity_category="diagnostic")
        publisher.publish_batch("hdd", {reading.key: reading})
        topic = "homeassistant/sensor/ugreen_telemetry_dxp4800pro/hdd_0123456789_pending_sectors/config"
        config = json.loads(next(payload for sent_topic, payload, _, _ in client.sent if sent_topic == topic))
        self.assertEqual(config["entity_category"], "diagnostic")
        self.assertIs(config["enabled_by_default"], False)

    def test_old_sensor_stays_unavailable_after_new_session(self):
        client = FakeClient()
        old = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session1")
        old.publish_batch("hdd", {
            "hdd_temperature": Reading("hdd_temperature", "HDD temperature", 40.0, "°C")
        })
        old.offline()
        new = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session2")
        new.publish_batch("fast", {
            "memory_usage": Reading("memory_usage", "Memory usage", 32.5, "%")
        })
        new.online()
        configs = {
            topic: json.loads(payload)
            for topic, payload, _, _ in client.sent
            if topic.endswith("/config")
        }
        old_config = configs[
            "homeassistant/sensor/ugreen_telemetry_dxp4800pro/hdd_temperature/config"
        ]
        self.assertEqual(old_config["availability"][0]["topic"], old.status_topic)
        self.assertNotEqual(old.status_topic, new.status_topic)
        self.assertIn((old.status_topic, "offline", 1, True), client.sent)
        self.assertIn((new.status_topic, "online", 1, True), client.sent)


if __name__ == "__main__":
    unittest.main()
