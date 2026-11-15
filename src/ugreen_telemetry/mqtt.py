from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from typing import Protocol

from .sensors import Reading

try:
    PACKAGE_VERSION = version("ugreen-telemetry-mqtt")
except PackageNotFoundError:
    PACKAGE_VERSION = "development"


class PublishResult(Protocol):
    rc: int

    def wait_for_publish(self, timeout: float = 10.0) -> object: ...

    def is_published(self) -> bool: ...


class Client(Protocol):
    def publish(self, topic: str, payload: str, qos: int, retain: bool) -> PublishResult: ...


class TelemetryPublisher:
    """Publish only sensor config, state and availability topics."""

    def __init__(self, client: Client, nas_id: str, nas_name: str, session_id: str):
        self.client = client
        self.nas_id = nas_id
        self.nas_name = nas_name
        self.base = f"ugreen_telemetry/{nas_id}"
        # A fresh topic prevents retained states from an earlier process from
        # becoming available again when its sensor is disabled in this run.
        self.status_topic = f"{self.base}/session/{session_id}/status"
        self.discovered: set[str] = set()
        self.active_by_group: dict[str, set[str]] = {}

    def reconnect(self) -> None:
        # Discovery must be offered again after a broker restart.
        self.discovered.clear()

    def _publish(self, topic: str, payload: str) -> None:
        result = self.client.publish(topic, payload, qos=1, retain=True)
        if result.rc != 0:
            raise RuntimeError(f"MQTT publish failed for {topic}: rc={result.rc}")
        result.wait_for_publish(timeout=10.0)
        if not result.is_published():
            raise TimeoutError(f"MQTT publish timeout for {topic}")

    def _sensor_base(self, key: str) -> str:
        return f"{self.base}/sensor/{key}"

    def _discovery(self, reading: Reading) -> None:
        if reading.key in self.discovered:
            return
        sensor_base = self._sensor_base(reading.key)
        config = {
            "name": reading.name,
            "unique_id": f"ugreen_telemetry_{self.nas_id}_{reading.key}",
            "state_topic": f"{sensor_base}/state",
            "availability": [
                {"topic": self.status_topic, "payload_available": "online", "payload_not_available": "offline"},
                {"topic": f"{sensor_base}/availability", "payload_available": "online", "payload_not_available": "offline"},
            ],
            "availability_mode": "all",
            "unit_of_measurement": reading.unit,
            "state_class": reading.state_class,
            "device": {
                "identifiers": [f"ugreen_telemetry_{self.nas_id}"],
                "name": self.nas_name,
                "manufacturer": "UGREEN",
                "model": "NAS telemetry",
            },
            "origin": {"name": "UGREEN Telemetry MQTT", "sw_version": PACKAGE_VERSION},
        }
        # A timestamp sensor has neither a unit nor a state class.
        for optional in ("unit_of_measurement", "state_class"):
            if config[optional] is None:
                del config[optional]
        if reading.device_class:
            config["device_class"] = reading.device_class
        if reading.entity_category:
            config["entity_category"] = reading.entity_category
            if reading.entity_category == "diagnostic":
                config["enabled_by_default"] = False
        topic = f"homeassistant/sensor/ugreen_telemetry_{self.nas_id}/{reading.key}/config"
        self._publish(topic, json.dumps(config, separators=(",", ":"), ensure_ascii=False))
        self.discovered.add(reading.key)

    def publish_batch(self, group: str, readings: dict[str, Reading]) -> None:
        current = set(readings)
        previous = self.active_by_group.get(group, set())
        for key in sorted(previous - current):
            self._publish(f"{self._sensor_base(key)}/availability", "offline")
        for key in sorted(current):
            reading = readings[key]
            self._discovery(reading)
            self._publish(f"{self._sensor_base(key)}/state", str(reading.value))
            self._publish(f"{self._sensor_base(key)}/availability", "online")
        self.active_by_group[group] = current

    def online(self) -> None:
        self._publish(self.status_topic, "online")

    def offline(self) -> None:
        self._publish(self.status_topic, "offline")
