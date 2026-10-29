# Installation on another UGREEN NAS

This is an experimental guide. The single-file installer was tested from a clean NAS-side setup on a DXP4800 Pro. Other models still need real-world testing.

## Prepare

1. Enable Home Assistant's MQTT integration and create a dedicated broker login for telemetry. Keep the broker address, port, username, and password outside the repository.
2. Enable Docker on the NAS and prepare an administrator SSH session. The installer requires Python 3, Docker Compose, systemd, and `/usr/sbin/smartctl`.
3. In UGOS Storage, identify the SATA disks and mounted data volumes you want to monitor. The installer displays Linux candidates, but you must confirm that the chosen disks belong to the intended pool.

The package runs a root-owned host helper for SMART reads and an unprivileged container for MQTT publishing. Installation creates `/root/ugreen-telemetry-mqtt`, two systemd unit files, a local configuration and MQTT secret, and a Docker image. These host files are necessary because a fully containerized SMART reader would need direct disk access. The installer does not overwrite an existing setup.

## Guided setup

Copy a release `.pyz` to a shared folder, verify its SHA-256 checksum against the release page, open SSH in that folder, and run:

```sh
sudo python3 ugreen-telemetry-mqtt-setup.pyz
```

Python unpacks the archive into a temporary private folder; `unzip` is not required. The wizard lists `sd*` disks and mounted `/volumeN` paths without opening SMART during discovery. Compare each disk with UGOS Storage before selecting it. A USB disk may also have an `sd*` name.

Select disks and volumes, enter a display name and stable NAS identifier, then the broker address, port, protocol, and dedicated username. Review the summary before confirming. The password prompt hides input; the password is not passed on the command line. A successful run starts the systemd timer, takes an initial snapshot, builds the Docker image, and starts the publisher. Home Assistant should then discover the device through the broker.

The broker must be reachable from the NAS. The first Docker build needs Internet access to fetch its base image and Python dependency. Home Assistant does not need a NAS administrator account.

## Explicit two-bay example

From an unpacked source checkout, an equivalent explicit command for two HDDs and `/volume2` is:

```sh
sudo python3 nas-install.py \
  --nas-id nas2bay --nas-name 'UGREEN 2 bay' \
  --mqtt-host 192.0.2.10 --mqtt-user ugreen_telemetry --mqtt-protocol 5 \
  --disk /dev/sda --disk /dev/sdb --volume archive=/volume2
```

Replace the example broker address, names, and disk paths. Repeat `--disk` or `--volume LABEL=/mount/path` as needed. The wizard automatically labels chosen volumes `data1`, `data2`, and so on. For an SSD SATA disk, repeat `--disk`; HDD count comes from sysfs, so the SSD does not count as an HDD. SSD temperature is published when available, while this project's SMART counters are HDD-only.

## Verify

```sh
systemctl is-enabled ugreen-telemetry-snapshot.timer
systemctl is-active ugreen-telemetry-snapshot.timer
systemctl show ugreen-telemetry-snapshot.service -p Result -p ExecMainStatus
cd /root/ugreen-telemetry-mqtt
docker compose -f compose.yaml -f compose.smart.yaml ps
docker compose -f compose.yaml -f compose.smart.yaml logs --tail=20 telemetry
```

Do not paste passwords, `.env`, or the secret file into an issue. Check the NAS device in Home Assistant's MQTT integration for current readings. SMART diagnostic entities are disabled by default on first registration. Home Assistant preserves previously recorded enabled/disabled choices when the same NAS identifier is reused; its entity list supports selecting and disabling multiple old diagnostic or obsolete volume entities at once.

The host helper uses `smartctl -d ata -n standby,0 -A` every 15 minutes. The `-n` option asks smartctl to skip sleeping disks, but controller behavior varies. A sleeping disk's reading becomes unavailable until a fresh valid sample. Confirm standby behavior on each NAS before depending on it.

An in-place updater and guided uninstaller do not exist yet. Do not rerun the installer against an existing installation. See [release and update policy](release-and-updates.md).
