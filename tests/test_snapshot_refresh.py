import os
import tempfile
import unittest
from pathlib import Path

from ugreen_telemetry.file_gate import FileChangeGate


class SnapshotRefreshTests(unittest.TestCase):
    def test_new_snapshot_is_read_before_next_interval(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshot.json"
            gate = FileChangeGate(path)
            self.assertTrue(gate.due(0.0, 0.0))

            path.write_text("{}", encoding="utf-8")
            os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            self.assertFalse(gate.due(11.0, 900.0))
            self.assertTrue(gate.due(60.0, 900.0))

            self.assertFalse(gate.due(61.0, 900.0))

            path.write_text("{\"version\":2}", encoding="utf-8")
            os.utime(path, ns=(2_000_000_000, 2_000_000_000))
            self.assertFalse(gate.due(119.0, 900.0))
            self.assertTrue(gate.due(120.0, 900.0))

    def test_interval_still_refreshes_unchanged_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshot.json"
            path.write_text("{}", encoding="utf-8")
            gate = FileChangeGate(path)
            self.assertTrue(gate.due(0.0, 0.0))
            self.assertFalse(gate.due(30.0, 900.0))
            self.assertTrue(gate.due(900.0, 900.0))


if __name__ == "__main__":
    unittest.main()
