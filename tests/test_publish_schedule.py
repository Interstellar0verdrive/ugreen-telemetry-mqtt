import json
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from ugreen_telemetry.main import groups_with_changed_readings, keep_last_reading, reading_group
from ugreen_telemetry.mqtt import TelemetryPublisher
from ugreen_telemetry.sensors import HDD_LAST_READING, Reading, read_smart_snapshot


class Result:
    rc = 0

    def wait_for_publish(self, timeout=10.0):
        return True

    def is_published(self):
        return True


class FakeClient:
    def __init__(self):
        self.sent = {}

    def publish(self, topic, payload, qos, retain):
        self.sent[topic] = payload
        return Result()


def hdd(key, value):
    return Reading(key, key, value, "°C", "temperature")


class PublishScheduleTests(unittest.TestCase):
    def test_storage_group_is_published_as_soon_as_the_first_snapshot_arrives(self):
        # At start the reader has not written its snapshot yet, so the first batch is empty.
        published = {"hdd": {}, "volume": {}}
        snapshot = {
            "hdd": {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                    "hdd_max_temperature": hdd("hdd_max_temperature", 44.0)},
            "volume": {},
        }
        self.assertEqual(groups_with_changed_readings(published, snapshot), {"hdd"})

        published["hdd"] = snapshot["hdd"]
        self.assertEqual(groups_with_changed_readings(published, snapshot), set())

    def test_a_new_sample_is_published_without_waiting_for_the_next_interval(self):
        # The reader and the publisher run on separate clocks. A sample written just after
        # the hourly publication must not wait an hour to reach Home Assistant.
        published = {"hdd": {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                             HDD_LAST_READING: hdd(HDD_LAST_READING, "2026-11-17T06:36:03+00:00")}}
        same_values = {"hdd": {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                               HDD_LAST_READING: hdd(HDD_LAST_READING, "2026-11-17T07:36:06+00:00")}}
        self.assertEqual(groups_with_changed_readings(published, same_values), {"hdd"})

    def test_an_unchanged_snapshot_keeps_the_normal_schedule(self):
        readings = {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0)}
        volume = {"volume_1_used": Reading("volume_1_used", "Volume 1 used", 40.0, "%")}
        published = {"hdd": dict(readings), "volume": dict(volume)}
        self.assertEqual(groups_with_changed_readings(published, {"hdd": readings, "volume": volume}), set())

    def test_a_disk_going_to_sleep_or_waking_up_is_published(self):
        both = {"hdd_a_temperature": hdd("hdd_a_temperature", 44.0),
                "hdd_b_temperature": hdd("hdd_b_temperature", 41.0)}
        asleep = {"hdd_a_temperature": both["hdd_a_temperature"]}
        self.assertEqual(groups_with_changed_readings({"hdd": both}, {"hdd": asleep}), {"hdd"})
        self.assertEqual(groups_with_changed_readings({"hdd": asleep}, {"hdd": both}), {"hdd"})


class LastReadingTests(unittest.TestCase):
    def snapshot(self, readings, disk_at):
        now = int(time.time())
        data = {"version": 3, "sampled_at": now, "disk_sampled_at": disk_at, "volume_sampled_at": now,
                "hdd_count": 2, "readings": readings, "volume_count": 0, "volumes": []}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "telemetry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return read_smart_snapshot(path, 2, 1800).readings

    def test_snapshot_reports_when_the_disks_were_read(self):
        disk_at = int(time.time()) - 120
        readings = self.snapshot(
            [{"key": "hdd_0123456789_temperature", "name": "HDD sda temperature", "temperature": 44}], disk_at)
        last = readings[HDD_LAST_READING]
        self.assertEqual(datetime.fromisoformat(last.value).timestamp(), disk_at)
        self.assertEqual(datetime.fromisoformat(last.value).utcoffset().total_seconds(), 0)
        self.assertEqual(reading_group(HDD_LAST_READING), "hdd")

    def test_no_hdd_reading_means_no_new_time(self):
        self.assertNotIn(HDD_LAST_READING, self.snapshot([], int(time.time())))

    def test_last_time_is_kept_while_every_disk_sleeps(self):
        first, last = keep_last_reading({}, None)
        self.assertEqual((first, last), ({}, None))
        stamp = Reading(HDD_LAST_READING, "HDD last reading", "2026-11-15T22:07:31+00:00", None, "timestamp", None)
        awake, last = keep_last_reading({HDD_LAST_READING: stamp}, None)
        self.assertIs(last, stamp)
        asleep, last = keep_last_reading({"volume_data_used_percent": hdd("volume_data_used_percent", 40.0)}, last)
        self.assertIs(asleep[HDD_LAST_READING], stamp)
        self.assertIn("volume_data_used_percent", asleep)

    def test_timestamp_discovery_has_no_unit_or_state_class(self):
        client = FakeClient()
        publisher = TelemetryPublisher(client, "dxp4800pro", "DXP4800 Pro", "session1")
        stamp = Reading(HDD_LAST_READING, "HDD last reading", "2026-11-15T22:07:31+00:00", None, "timestamp", None)
        publisher.publish_batch("hdd", {HDD_LAST_READING: stamp, "hdd_a_temperature": hdd("hdd_a_temperature", 44.0)})
        config = json.loads(client.sent["homeassistant/sensor/ugreen_telemetry_dxp4800pro/hdd_last_reading/config"])
        self.assertEqual(config["device_class"], "timestamp")
        self.assertEqual(config["unique_id"], "ugreen_telemetry_dxp4800pro_hdd_last_reading")
        self.assertNotIn("unit_of_measurement", config)
        self.assertNotIn("state_class", config)
        self.assertNotIn("entity_category", config)
        self.assertEqual(client.sent["ugreen_telemetry/dxp4800pro/sensor/hdd_last_reading/state"],
                         "2026-11-15T22:07:31+00:00")
        temperature = json.loads(client.sent["homeassistant/sensor/ugreen_telemetry_dxp4800pro/hdd_a_temperature/config"])
        self.assertEqual((temperature["unit_of_measurement"], temperature["state_class"]), ("°C", "measurement"))


if __name__ == "__main__":
    unittest.main()
