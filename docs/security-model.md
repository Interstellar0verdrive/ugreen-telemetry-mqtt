# Security model and published data

## Access on the NAS

The SMART helper runs as root because an ordinary user could not open SATA devices on the tested DXP4800 Pro. It reads only selected device paths and writes a small JSON snapshot. It does not connect to MQTT.

The MQTT container is not privileged. It has no Docker socket, block device, data-volume mount, or inbound port. It reads host sysfs and the SMART snapshot through read-only mounts, runs as UID 10001, has a read-only root filesystem, and drops Linux capabilities. Sysfs can expose hardware metadata, so the container should still be trusted to read it.

Use a dedicated MQTT login. Its password is stored on the NAS at `/root/ugreen-telemetry-mqtt/secrets/mqtt_password.txt`. The file must be readable by the container process, while its parent directory is accessible only to the NAS administrator. Someone with administrative control of Docker on the NAS can still read the secret.

## Data sent to the broker

MQTT messages contain the chosen NAS name and identifier, Linux disk names and derived sensor identifiers, temperatures, selected SMART counters, volume usage, CPU, memory, and uptime. They do not contain disk serial numbers, filenames, full SMART dumps, volume mount paths, or NAS credentials.

Linux disk names and identifiers derived from hardware paths can change after moving disks or changing the NAS. Home Assistant may then create new entities. Retained MQTT Discovery messages can also leave obsolete entities until they are explicitly cleaned up.

## Network

With `MQTT_TLS=false`, MQTT traffic and its password travel unencrypted over the local network. Use TLS with a verifiable certificate when the network path is not trusted. If you depend on broker ACLs to restrict the dedicated login, verify that the broker actually applies them; do not infer isolation from the username alone. A report about custom ACL behavior in Home Assistant's Mosquitto add-on is tracked [upstream](https://github.com/home-assistant/addons/issues/4721).

The project publishes telemetry only and accepts no MQTT commands. If readings drive fan or safety automations, set plausible limits and a safe behavior when a sensor is unavailable or stale.

## Disk standby

The helper calls `smartctl -d ata -n standby,0 -A` to request a non-waking read. Firmware and controllers may behave differently. Use [monitoring impact](monitoring-impact.md) to compare disk counters before and after enabling the bridge.
