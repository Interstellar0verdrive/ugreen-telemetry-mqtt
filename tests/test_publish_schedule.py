import unittest

from ugreen_telemetry.main import groups_with_new_readings
from ugreen_telemetry.mqtt import TelemetryPublisher
from ugreen_telemetry.sensors import Reading


class Result:
    rc = 0

    def wait_for_publish(self, timeout=10.0):
        return True

    def is_published(self):
        return True


class FakeClient:
    def publish(self, topic, payload, qos, retain):
        return Result()


def hdd(key, value):
    return Reading(key, key, value, "°C", "temperature")


class PublishScheduleTests(unittest.TestCase):
    def test_storage_group_is_published_as_soon_as_the_first_snapshot_arrives(self):
        publisher = TelemetryPublisher(FakeClient(), "dxp4800pro", "DXP4800 Pro", "session1")
        # At start the reader has not written its snapshot yet, so the first batch is empty.
        publisher.publish_batch("hdd", {})
        publisher.publish_batch("volume", {})

        snapshot = {
            "hdd": {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                    "hdd_max_temperature": hdd("hdd_max_temperature", 44.0)},
            "volume": {},
        }
        self.assertEqual(groups_with_new_readings(publisher.active_by_group, snapshot), {"hdd"})

        publisher.publish_batch("hdd", snapshot["hdd"])
        self.assertEqual(groups_with_new_readings(publisher.active_by_group, snapshot), set())

    def test_new_values_for_known_sensors_keep_the_normal_schedule(self):
        publisher = TelemetryPublisher(FakeClient(), "dxp4800pro", "DXP4800 Pro", "session1")
        publisher.publish_batch("hdd", {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0)})
        newer = {"hdd": {"hdd_a_temperature": hdd("hdd_a_temperature", 45.0)}}
        self.assertEqual(groups_with_new_readings(publisher.active_by_group, newer), set())

    def test_a_disk_going_to_sleep_waits_but_a_disk_waking_up_is_published(self):
        publisher = TelemetryPublisher(FakeClient(), "dxp4800pro", "DXP4800 Pro", "session1")
        both = {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                "hdd_b_temperature": hdd("hdd_b_temperature", 41.0)}
        publisher.publish_batch("hdd", both)
        asleep = {"hdd": {"hdd_a_temperature": both["hdd_a_temperature"]}}
        self.assertEqual(groups_with_new_readings(publisher.active_by_group, asleep), set())

        publisher.publish_batch("hdd", asleep["hdd"])
        self.assertEqual(groups_with_new_readings(publisher.active_by_group, {"hdd": both}), {"hdd"})


if __name__ == "__main__":
    unittest.main()
