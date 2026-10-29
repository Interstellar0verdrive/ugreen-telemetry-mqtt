# UGREEN Telemetry MQTT

Experimental, outbound-only telemetry from a UGREEN NAS to Home Assistant through MQTT Discovery.

> A browser-based UGOS Docker setup is under development. On the DXP4800 Pro, its two-container pilot now publishes to the real Home Assistant broker under the historical device ID. The NAS, broker add-on, and Home Assistant Core were restarted separately on October 27, 2026; the pilot resumed publishing without manual container starts or duplicate devices. The NAS logged sustained HDD sleep while the isolated reader ran, but a specific standby-skip sample was not directly verified. A local upgrade between two code versions and rollback passed; a published-image update remains untested. See the [UI prototype notes](docs/ugos-ui-prototype.md). The documented SSH installer remains the established installation path for now.

The intended no-SSH installation is one UGOS Docker project using a published image and a browser wizard. It is still a development path. Its two containers use the same image: one handles setup and MQTT, while the other reads selected disks without network access. The [GHCR Compose template](compose.ugos.ghcr.example.yaml) and [release workflow](.github/workflows/publish-image.yml) are available for inspection. Private `v0.3.0.dev1` and `v0.3.0.dev2` prerelease images have been published for an upgrade test; a registry-image installation on UGOS has not yet been verified.

For an existing host-installer deployment, see the [draft migration and rollback plan](docs/migration-from-host-installer.md). It is not a tested cutover procedure yet.

I built this primarily for my own NAS and am sharing it in case it helps someone else. It is a personal project, not an official UGREEN or Home Assistant integration. I cannot promise maintenance, support, compatibility with every model, or a release schedule. Contributions and reports from other devices are welcome. The MIT license allows anyone to fork and adapt the code.

## Why this exists

Other NAS monitoring projects already exist and may be a better fit for many people. For my setup, I wanted a smaller path that keeps the NAS administrator account on the NAS. A host-side helper reads SMART and volume usage locally; a restricted container publishes selected readings to MQTT. Home Assistant only connects to the broker. It never receives NAS administrator credentials. This separation was the reason for writing the project, not a criticism of other approaches.

## Current status

This is a **prototype**, not yet a supported public release. Guided installation, four SATA HDDs, one data volume, the systemd timer, Docker publisher, MQTT 5, and Home Assistant Discovery were tested from a clean NAS-side install on a DXP4800 Pro running UGOS Pro 1.20.0.0142. The browser pilot was tested against the real broker, through separate NAS, broker add-on, and Home Assistant Core restarts, and through a local `0.3.0.dev1` → `0.3.0.dev2` code upgrade and rollback. A two-bay layout has simulated tests only. Compatibility with another UGREEN model, a directly observed standby-skip sample, a registry-image update, and configuration migrations still need validation.

| Reading | Interval | Home Assistant default |
| --- | --- | --- |
| CPU usage, memory usage | 60 seconds | Enabled |
| CPU temperature, detected SSD/NVMe temperature, HDD temperature, maximum HDD temperature, volume usage, uptime | 15 minutes | Enabled |
| Supported HDD SMART counters | 15 minutes | Disabled; opt in per entity |

The number of readings depends on the selected disks, mounted volumes, and sensors exposed by the NAS. A missing SMART attribute does not appear as zero.

## Inspect the code before installing

The complete source is in this repository: [`nas-install.py`](nas-install.py) performs setup, [`host-smart-snapshot.py`](host-smart-snapshot.py) reads selected SATA disks and volumes, and [`src/ugreen_telemetry/`](src/ugreen_telemetry/) publishes to MQTT. The `.pyz` download is a ZIP archive containing these readable source files, not an opaque executable. You can inspect it before running it:

```sh
python3 -m zipfile -l ugreen-telemetry-mqtt-setup.pyz
python3 -m zipfile -e ugreen-telemetry-mqtt-setup.pyz inspected-source
```

Release downloads should be built from a tagged commit and accompanied by a SHA-256 checksum; GitHub also provides a source archive for each tag.

## Install a fresh instance

Prerequisites: UGOS Pro with Docker Compose, Python 3, `/usr/sbin/smartctl`, systemd, administrator access on the NAS for setup and SMART reads, a reachable MQTT broker, and Home Assistant's MQTT integration. Create a dedicated MQTT login on the broker. Do not put its password in a command argument or GitHub issue.

Copy the release `.pyz` to a shared folder on the NAS, verify its published SHA-256 checksum, then run from SSH:

```sh
sudo python3 ugreen-telemetry-mqtt-setup.pyz
```

The guided setup lists candidate SATA disks and mounted volumes. Check the disk choices against UGOS Storage, enter the broker address and dedicated MQTT username, review the targets, then enter the password at the hidden prompt. Setup creates a private installation under `/root/ugreen-telemetry-mqtt`, a systemd timer for SMART snapshots, and a Docker Compose service for MQTT. The first image build needs Internet access. Details and a two-bay example are in [installation guidance](docs/installation.md).

The installer **refuses to overwrite an existing installation**. Do not rerun it as an update. An in-place updater and guided uninstaller are still planned; the [changelog](CHANGELOG.md) and [release and update policy](docs/release-and-updates.md) describe what is and is not supported today.

## Behavior after restarts

The SSH installer enables the systemd timer, and Compose uses `restart: unless-stopped` for its publisher. If that container was intentionally stopped, Docker leaves it stopped after reboot. The timer does not replay missed samples. The separate browser pilot uses two containers and a RAM-backed snapshot: both came back after an October 27 NAS reboot; HDD temperatures returned on the next reader sample. The same Home Assistant device received fresh CPU and memory values after separate broker add-on and Home Assistant Core restarts. A local two-code-version upgrade and rollback also recovered the existing device and HDD readings; published-image upgrades remain untested. See [restart and storage notes](docs/restarts-and-storage.md).

## Storage and load

The publisher retains only the latest MQTT values, rather than an ever-growing MQTT time series. Home Assistant's Recorder stores changed sensor states in its database; its default detailed-history retention is 10 days, while eligible hourly long-term statistics are kept until removed. Repeated unchanged MQTT values are filtered by Home Assistant because this project does not set `force_update`. On the tested four-HDD setup, two sensors publish once a minute and ten active sensors every 15 minutes. That is at most 3,840 state publications per day, not necessarily 3,840 Recorder writes. Check your own Recorder configuration and database growth if you have changed its defaults. [Restart and storage notes](docs/restarts-and-storage.md) explain the estimate and how to opt out of recording particular entities.

## Security and limitations

The host helper runs as root because ordinary users could not open the SATA devices on the tested NAS. It writes a small allowlisted JSON snapshot. The MQTT container runs as UID 10001, has a read-only root filesystem, drops Linux capabilities, has no inbound port or Docker socket, and mounts only sysfs and the snapshot read-only. The dedicated MQTT password stays on the NAS. MQTT without TLS still sends that password in clear text on the local network; use TLS on an untrusted network and verify any broker ACL you rely on. See the [security model](docs/security-model.md).

`smartctl -n standby,0` attempts to avoid waking sleeping disks, but controller behavior varies. During an approximately eight-hour trial on the DXP4800 Pro, HDD Start/Stop and Load Cycle counters did not increase; UGOS disk suspension was disabled, so this does not prove sleep-safe polling. See [monitoring impact](docs/monitoring-impact.md).

If Home Assistant already knows the same NAS from an earlier version, it keeps existing enabled/disabled entity choices. Reinstalling the publisher does not reset them. Use Home Assistant's multi-select entity action to disable old diagnostic counters or obsolete volume labels. New entities use the package's defaults.

## Repository layout

| Path | Purpose |
| --- | --- |
| `nas-install.py`, `tools/` | Guided setup and `.pyz` builder |
| `host-smart-snapshot.py`, `systemd/` | Local SMART/volume sampling and timer |
| `src/ugreen_telemetry/` | Unprivileged MQTT publisher |
| `compose*.yaml`, `Dockerfile` | Container configuration and build |
| `.github/workflows/` | Tests and GHCR image publication on release |
| `tests/` | Simulated sensor, installer, and MQTT tests |
| `docs/` | Installation, restarts, security, impact, and release notes |

Run local tests with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [contributing](CONTRIBUTING.md) before sharing test output. Do not post credentials, disk serial numbers, full SMART dumps, or personal paths.
