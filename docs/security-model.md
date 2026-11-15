# Security model and published data

## Two containers, two sets of permissions

Docker fixes a container's device access when it starts. A wizard cannot discover a disk and grant itself access to that disk later without the Docker control socket or broad device access from the start. The project therefore splits the work between two containers from the same image, managed as one UGOS Docker project.

**`setup`** serves the wizard and publishes to MQTT. It runs as UID 10001 with a read-only root filesystem, drops all Linux capabilities, and has no Docker socket, block device, or raw disk access. It reads host sysfs read-only for CPU, memory and temperature sensors, which can expose hardware metadata, so the container should still be trusted to read it. It stores the configuration and the MQTT password in two separate named volumes.

**`reader`** reads SMART data and volume space. It has no network, no MQTT password and no web port. It runs as root because ordinary users could not open the SATA devices on the tested NAS. It sees the host `/dev` read-only, has a device rule that allows reads from SATA block devices (major 8), and receives only `CAP_SYS_RAWIO`. It opens only the `/dev/sd*` paths selected in the wizard and the selected volume mounts, which are read-only. It writes a small allowlisted JSON snapshot to a RAM-backed volume shared with `setup`.

Neither container is privileged, and neither has the Docker socket. A read-only device mapping does not guarantee that every possible device command is harmless; the reader's access is the part to review first, and must be checked again for each supported hardware layout.

### Why `CAP_SYS_RAWIO` and the SAT path

On the tested DXP4800 Pro, which runs Linux 6.18, the ATA power-mode ioctl needs both `CAP_SYS_ADMIN` and `CAP_SYS_RAWIO`. Without them, smartctl reports the disk as sleeping, which hides the permission error. The SAT path (`smartctl -d sat`) works with `CAP_SYS_RAWIO` alone, so the reader uses it and does not need `CAP_SYS_ADMIN`. The web process never receives raw I/O capability.

## The setup token and the MQTT password

The setup token is printed in the `setup` container's log. It authenticates the person configuring the page; it is not a credential between the two containers. The saved MQTT password can be revealed in the wizard only after token authentication.

Use a dedicated MQTT login. Its password is stored on the NAS in the `setup` container's secrets volume. Someone with administrative control of Docker on the NAS can still read it.

## Data sent to the broker

MQTT messages contain the chosen NAS name and identifier, Linux disk names and derived sensor identifiers, temperatures, selected SMART counters, volume usage, CPU, memory, and uptime. They do not contain disk serial numbers, filenames, full SMART dumps, volume mount paths, or NAS credentials.

Each HDD's sensor identifier is derived from its hardware path, so it stays stable when Linux names the disks in a different order. The display name, such as "HDD sdb temperature", uses the current Linux name. Moving disks or changing the NAS can still create new entities. Retained MQTT Discovery messages can also leave obsolete entities until they are explicitly cleaned up.

## Network

The setup page uses local HTTP. The token and the MQTT password cross the LAN unencrypted while you configure it, so use it only on a trusted network and never expose port 8765 through a router or reverse proxy without proper HTTPS and access control.

With TLS off, MQTT traffic and its password also travel unencrypted over the local network. Use TLS with a verifiable certificate when the network path is not trusted. If you depend on broker ACLs to restrict the dedicated login, verify that the broker actually applies them; do not infer isolation from the username alone. A report about custom ACL behavior in Home Assistant's Mosquitto add-on is tracked [upstream](https://github.com/home-assistant/addons/issues/4721).

The project publishes telemetry only and accepts no MQTT commands. If readings drive fan or safety automations, set plausible limits and a safe behavior when a sensor is unavailable or stale.

## Disk standby

The reader calls `smartctl -d sat -n standby,0 -A` without `--allow-wake`, to request a reading that skips sleeping disks. Firmware and controllers may behave differently. Use [monitoring impact](monitoring-impact.md) to compare disk counters before and after enabling the project.
