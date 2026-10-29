"""A local MQTT broker stub verifies the real Paho publishing path."""

import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


def read_exact(stream, count):
    data = bytearray()
    while len(data) < count:
        part = stream.read(count - len(data))
        if not part:
            raise EOFError
        data.extend(part)
    return bytes(data)


def read_packet(stream):
    first = read_exact(stream, 1)[0]
    multiplier = 1
    size = 0
    while True:
        byte = read_exact(stream, 1)[0]
        size += (byte & 127) * multiplier
        if byte < 128:
            break
        multiplier *= 128
    return first, read_exact(stream, size)


def variable_integer(data, offset):
    multiplier = 1
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value += (byte & 127) * multiplier
        if byte < 128:
            return value, offset
        multiplier *= 128


class MQTTHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            while True:
                header, body = read_packet(self.rfile)
                packet_type = header >> 4
                self.server.packet_types.append(packet_type)
                if packet_type == 1:  # CONNECT
                    protocol_level = body[6]
                    self.server.protocol_levels.append(protocol_level)
                    self.wfile.write(b"\x20\x03\x00\x00\x00" if protocol_level == 5 else b"\x20\x02\x00\x00")
                elif packet_type == 3:  # PUBLISH
                    length = int.from_bytes(body[:2], "big")
                    topic = body[2 : 2 + length].decode("utf-8")
                    index = 2 + length
                    qos = (header >> 1) & 3
                    message_id = body[index : index + 2] if qos else b""
                    index += 2 if qos else 0
                    if self.server.protocol_levels[-1] == 5:
                        properties_length, index = variable_integer(body, index)
                        index += properties_length
                    self.server.messages.append((topic, body[index:].decode("utf-8")))
                    if qos == 1:
                        self.wfile.write(b"\x40\x02" + message_id)
                elif packet_type == 12:  # PINGREQ
                    self.wfile.write(b"\xd0\x00")
                elif packet_type == 14:  # DISCONNECT
                    return
                self.wfile.flush()
        except (EOFError, BrokenPipeError, ConnectionResetError):
            return


class LocalBroker(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), MQTTHandler)
        self.messages = []
        self.packet_types = []
        self.protocol_levels = []


@unittest.skipUnless(__import__("importlib").util.find_spec("paho"), "paho-mqtt not installed")
class EndToEndTests(unittest.TestCase):
    def _exercise_protocol(self, protocol):
        with tempfile.TemporaryDirectory() as temp, LocalBroker() as broker:
            root = Path(temp)
            proc = root / "proc"
            proc.mkdir()
            (proc / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\n", encoding="utf-8")
            (proc / "meminfo").write_text(
                "MemTotal: 1000 kB\nMemAvailable: 250 kB\n", encoding="utf-8"
            )
            (proc / "uptime").write_text("7200.00 100.00\n", encoding="utf-8")
            sys_root = root / "sys"
            (sys_root / "block").mkdir(parents=True)
            (sys_root / "class" / "hwmon").mkdir(parents=True)
            secret = root / "password"
            secret.write_text("test-only-password\n", encoding="utf-8")
            thread = threading.Thread(target=broker.serve_forever, daemon=True)
            thread.start()
            env = {
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                "NAS_ID": "testnas",
                "NAS_NAME": "Test NAS",
                "MQTT_HOST": "127.0.0.1",
                "MQTT_PORT": str(broker.server_address[1]),
                "MQTT_USER": "test",
                "MQTT_PROTOCOL": protocol,
                "MQTT_PASSWORD_FILE": str(secret),
                "PROC_ROOT": str(proc),
                "SYS_ROOT": str(sys_root),
            }
            process = subprocess.Popen(
                [sys.executable, "-m", "ugreen_telemetry.main"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    received = {topic for topic, _ in broker.messages}
                    if any(topic.endswith("/memory_usage/state") for topic in received) and any(
                        topic.endswith("/uptime/state") for topic in received
                    ):
                        break
                    time.sleep(0.05)
                else:
                    self.fail(f"No MQTT state received: {process.stderr.read() if process.poll() is not None else ''}")
            finally:
                process.terminate()
                _, stderr = process.communicate(timeout=5)
                broker.shutdown()
                thread.join(timeout=2)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(broker.protocol_levels, [5 if protocol == "5" else 4])
            self.assertNotIn(8, broker.packet_types)  # SUBSCRIBE never sent.
            topics = [topic for topic, _ in broker.messages]
            self.assertIn("homeassistant/sensor/ugreen_telemetry_testnas/memory_usage/config", topics)
            self.assertIn("homeassistant/sensor/ugreen_telemetry_testnas/uptime/config", topics)
            self.assertTrue(any(topic.startswith("ugreen_telemetry/testnas/session/") and topic.endswith("/status") for topic in topics))
            self.assertTrue(
                all(
                    topic.startswith("ugreen_telemetry/testnas/")
                    or topic.startswith("homeassistant/sensor/ugreen_telemetry_testnas/")
                    for topic in topics
                )
            )

    def test_mqtt_311_publication_only(self):
        self._exercise_protocol("3.1.1")

    def test_mqtt_5_publication_only(self):
        self._exercise_protocol("5")


if __name__ == "__main__":
    unittest.main()
