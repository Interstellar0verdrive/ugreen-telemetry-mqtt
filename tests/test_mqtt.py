import json
import time
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


class SlowResult:
    """A QoS 1 publication that the broker acknowledges only when the test says so."""

    def __init__(self, rc=0):
        self.rc = rc
        self.acknowledged = False

    def wait_for_publish(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while not self.acknowledged and time.monotonic() < deadline:
            time.sleep(0.005)

    def is_published(self):
        return self.acknowledged


class SlowClient:
    def __init__(self):
        self.results = []

    def publish(self, topic, payload, qos, retain):
        result = SlowResult()
        self.results.append(result)
        return result


class SlowBrokerTests(unittest.TestCase):
    def setUp(self):
        self.client = SlowClient()
        self.publisher = TelemetryPublisher(self.client, "dxp4800pro", "DXP4800 Pro", "session1")
        self.batch = {"cpu_usage": Reading("cpu_usage", "CPU usage", 15.0, "%"),
                      "memory_usage": Reading("memory_usage", "Memory usage", 32.5, "%")}

    def test_whole_batch_is_queued_before_waiting(self):
        self.publisher.publish_batch("fast", self.batch)
        # Two sensors: discovery, state and availability each, sent without waiting.
        self.assertEqual(len(self.client.results), 6)
        self.assertEqual(self.publisher.active_by_group["fast"], set(self.batch))

    def test_slow_acknowledgement_shares_one_deadline(self):
        self.publisher.publish_batch("fast", self.batch)
        started = time.monotonic()
        with self.assertLogs("ugreen_telemetry", "WARNING") as logs:
            self.assertFalse(self.publisher.flush(timeout=0.2))
        self.assertLess(time.monotonic() - started, 0.6)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("6 message(s)", logs.output[0])
        self.assertIn("stay queued", logs.output[0])

    def test_one_warning_per_episode_and_a_note_on_recovery(self):
        self.publisher.publish_batch("fast", self.batch)
        with self.assertLogs("ugreen_telemetry", "WARNING"):
            self.publisher.flush(timeout=0.05)
        self.publisher.publish_batch("fast", self.batch)
        with self.assertNoLogs("ugreen_telemetry", "WARNING"):
            self.assertFalse(self.publisher.flush(timeout=0.05))
        for result in self.client.results[:-1]:
            result.acknowledged = True
        with self.assertNoLogs("ugreen_telemetry", "INFO"):
            self.assertFalse(self.publisher.flush(timeout=0.05))
        self.client.results[-1].acknowledged = True
        with self.assertLogs("ugreen_telemetry", "INFO") as logs:
            self.assertTrue(self.publisher.flush(timeout=0.05))
        self.assertIn("acknowledges messages again", logs.output[0])
        with self.assertNoLogs("ugreen_telemetry", "INFO"):
            self.assertTrue(self.publisher.flush())

    def test_publication_refused_by_the_client_is_still_an_error(self):
        self.client.publish = lambda topic, payload, qos, retain: SlowResult(rc=4)
        with self.assertRaises(RuntimeError):
            self.publisher.publish_batch("fast", self.batch)
        self.assertNotIn("fast", self.publisher.active_by_group)


if __name__ == "__main__":
    unittest.main()
