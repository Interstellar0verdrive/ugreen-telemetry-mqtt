# Contributing

This is an independent personal prototype. Reports from other UGREEN models are useful, especially two-bay NASes and setups with SATA SSDs or NVMe drives. Contributions are welcome, but there is no promised review or release schedule. The MIT license allows forks and adaptations.

For a compatibility report, include the NAS model, UGOS Pro version, number and type of disks, number of mounted data volumes, installer result, and which sensors appear in Home Assistant. Do **not** post passwords, serial numbers, private network addresses, personal paths, full SMART dumps, `.env`, `host.json`, or the MQTT secret. Redact any output before submitting it.

For code changes, add a meaningful test using simulated data and run:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

A simulated two-bay test does not establish real hardware compatibility. Only a test on the actual NAS can show whether its SATA controller respects `smartctl -n standby,0` or exposes the expected `hwmon` sensors.
