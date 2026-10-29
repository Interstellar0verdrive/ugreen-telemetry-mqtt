<img align="right" src="src/ugreen_telemetry/web_assets/app-icon-light.png#gh-light-mode-only" width="96" alt="UGREEN Telemetry app icon, light variant">
<img align="right" src="src/ugreen_telemetry/web_assets/app-icon-dark.png#gh-dark-mode-only" width="96" alt="UGREEN Telemetry app icon, dark variant">

# UGREEN Telemetry MQTT

<p align="center">
  <img src="docs/images/readme-preview-light.svg#gh-light-mode-only" alt="Light-mode mockup of Readings to publish" width="100%">
  <img src="docs/images/readme-preview-dark.svg#gh-dark-mode-only" alt="Dark-mode mockup of Readings to publish" width="100%">
</p>

Experimental, outbound-only telemetry from a UGREEN NAS to Home Assistant through MQTT Discovery.

> A browser-based UGOS Docker setup is under development. On the DXP4800 Pro, its two-container pilot now publishes to the real Home Assistant broker under the historical device ID. The NAS, broker add-on, and Home Assistant Core were restarted separately on October 27, 2026; the pilot resumed publishing without manual container starts or duplicate devices. The NAS logged sustained HDD sleep while the isolated reader ran, but a specific standby-skip sample was not directly verified. Both a local code-version upgrade and a private GHCR image upgrade with rollback passed. A public release update remains untested. See the [UI prototype notes](docs/ugos-ui-prototype.md). The documented SSH installer remains the established installation path for now.

The intended no-SSH installation is one UGOS Docker project using a published image and a browser wizard. It is still a development path. Its two containers use the same image: one handles setup and MQTT, while the other reads selected disks without network access. The [GHCR Compose template](compose.ugos.ghcr.example.yaml) and [release workflow](.github/workflows/publish-image.yml) are available for inspection. Private `v0.3.0.dev1` and `v0.3.0.dev2` prerelease images were pulled by UGOS and tested in an upgrade and rollback of the existing pilot. A fresh installation from a public image has not been verified.

For an existing host-installer deployment, see the [draft migration and rollback plan](docs/migration-from-host-installer.md). It is not a tested cutover procedure yet.

I built this primarily for my own NAS and am sharing it in case it helps someone else. It is a personal project, not an official UGREEN or Home Assistant integration. I cannot promise maintenance, support, compatibility with every model, or a release schedule. Contributions and reports from other devices are welcome. The MIT license allows anyone to fork and adapt the code.

## Why this exists

Other NAS monitoring projects already exist and may be a better fit for many people. For my setup, I wanted a smaller path that keeps the NAS administrator account on the NAS. A host-side helper reads SMART and volume usage locally; a restricted container publishes selected readings to MQTT. Home Assistant only connects to the broker. It never receives NAS administrator credentials. This separation was the reason for writing the project, not a criticism of other approaches.

The developing browser pilot keeps the same separation within one UGOS Docker project. Its reader container accesses the selected disks and writes a RAM-backed snapshot without network access. Its setup/publisher container uses that snapshot and the dedicated MQTT login to publish readings. The SSH installer described below uses a host helper instead of a reader container.

## Current status

This is a **prototype**, not yet a supported public release. Guided installation, four SATA HDDs, one data volume, the systemd timer, Docker publisher, MQTT 5, and Home Assistant Discovery were tested from a clean NAS-side install on a DXP4800 Pro running UGOS Pro 1.20.0.0142. The browser pilot was tested against the real broker, through separate NAS, broker add-on, and Home Assistant Core restarts, a local `0.3.0.dev1` → `0.3.0.dev2` code upgrade and rollback, and a private GHCR `dev1` → `dev2` → `dev1` image upgrade followed by restoration of the local image. A two-bay layout has simulated tests only. Compatibility with another UGREEN model, a directly observed standby-skip sample, a public image update, and configuration migrations still need validation.

| Reading | Interval | Home Assistant default |
| :--- | :--- | :--- |
| CPU usage, memory usage | 60 seconds | Enabled |
| CPU temperature, detected SSD/NVMe temperature, HDD temperature, maximum HDD temperature, volume usage, uptime | 15 minutes | Enabled |
| Supported HDD SMART counters | 15 minutes | Disabled; opt in per entity |

The number of readings depends on the selected disks, mounted volumes, and sensors exposed by the NAS. A missing SMART attribute does not appear as zero.

The browser pilot lets you select each reading and its interval. These mockups use the current wizard labels and the choices from the tested DXP4800 Pro pilot; actual choices depend on the NAS. See the [illustrated wizard guide](docs/ugos-ui-prototype.md).

<p align="center">
  <img src="docs/images/storage-preview-light.svg#gh-light-mode-only" width="100%" alt="Light-mode mockup of Disks and volumes">
  <img src="docs/images/storage-preview-dark.svg#gh-dark-mode-only" width="100%" alt="Dark-mode mockup of Disks and volumes">
</p>

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

For a preview of the separate browser pilot's token, NAS/MQTT, and disk selection screens, see the [illustrated UGOS UI guide](docs/ugos-ui-prototype.md). Those screens are not part of the SSH installer above.

The installer **refuses to overwrite an existing installation**. Do not rerun it as an update. An in-place updater and guided uninstaller are still planned; the [changelog](CHANGELOG.md) and [release and update policy](docs/release-and-updates.md) describe what is and is not supported today.

## Behavior after restarts

The SSH installer enables the systemd timer, and Compose uses `restart: unless-stopped` for its publisher. If that container was intentionally stopped, Docker leaves it stopped after reboot. The timer does not replay missed samples. The separate browser pilot uses two containers and a RAM-backed snapshot: both came back after an October 27 NAS reboot; HDD temperatures returned on the next reader sample. The same Home Assistant device received fresh CPU and memory values after separate broker add-on and Home Assistant Core restarts. A local code-version upgrade with rollback recovered the existing device and HDD readings. A later private GHCR image upgrade with rollback preserved settings and the same device; fresh HDD values were not confirmed in that specific test. See [restart and storage notes](docs/restarts-and-storage.md).

## Storage and load

The publisher retains only the latest MQTT values, rather than an ever-growing MQTT time series. Home Assistant's Recorder stores changed sensor states in its database; its default detailed-history retention is 10 days, while eligible hourly long-term statistics are kept until removed. Repeated unchanged MQTT values are filtered by Home Assistant because this project does not set `force_update`. On the tested four-HDD setup, two sensors publish once a minute and ten active sensors every 15 minutes. That is at most 3,840 state publications per day, not necessarily 3,840 Recorder writes. Check your own Recorder configuration and database growth if you have changed its defaults. [Restart and storage notes](docs/restarts-and-storage.md) explain the estimate and how to opt out of recording particular entities.

## Security and limitations

The host helper runs as root because ordinary users could not open the SATA devices on the tested NAS. It writes a small allowlisted JSON snapshot. The MQTT container runs as UID 10001, has a read-only root filesystem, drops Linux capabilities, has no inbound port or Docker socket, and mounts only sysfs and the snapshot read-only. The dedicated MQTT password stays on the NAS. MQTT without TLS still sends that password in clear text on the local network; use TLS on an untrusted network and verify any broker ACL you rely on. See the [security model](docs/security-model.md).

The developing browser pilot asks for the dedicated MQTT login in its NAS and MQTT screen. The password stays on the NAS and is hidden by default in the browser wizard.

`smartctl -n standby,0` attempts to avoid waking sleeping disks, but controller behavior varies. During an approximately eight-hour trial on the DXP4800 Pro, HDD Start/Stop and Load Cycle counters did not increase; UGOS disk suspension was disabled, so this does not prove sleep-safe polling. See [monitoring impact](docs/monitoring-impact.md).

If Home Assistant already knows the same NAS from an earlier version, it keeps existing enabled/disabled entity choices. Reinstalling the publisher does not reset them. Use Home Assistant's multi-select entity action to disable old diagnostic counters or obsolete volume labels. New entities use the package's defaults.

## Repository layout

| Path | Purpose |
| :--- | :--- |
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
