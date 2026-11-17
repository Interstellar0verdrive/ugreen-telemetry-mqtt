# Changelog

All notable changes are documented here. Versions before 0.3.0b1 were private development builds.

## Unreleased

- HDD, volume and SMART diagnostic readings reach Home Assistant within a minute of each new sample. Before, a sample written just after the group's scheduled publication waited a whole interval: with HDD temperatures every 60 minutes, my NAS showed readings one hour old for a whole morning. A disk that goes to sleep is now also shown as unavailable at the sample that finds it asleep.
- The setup page loads its logo as a 176-pixel WebP image, twice its displayed size, and uses 64-pixel favicons. Before, each visit downloaded about 1.1 MB of 1024-pixel PNG icons; the page now needs under 20 KB for them.
- The installation wheels no longer remain in a layer of the container image. With the smaller icons, the image is about 4 MB smaller.
- The setup container no longer logs a `BrokenPipeError` traceback when a browser closes the page or cancels a download while the setup page is still loading. Other errors are still logged.
- Before publishing, the release workflow starts both services from the amd64 and the arm64 image and checks the version, the setup page, and a clean stop. Every push runs the same check.

## 0.3.0b3 — 2026-11-16

An update check in the setup page. No configuration changes are needed, and existing Home Assistant entities keep their identifiers.

- **Check for updates** in the setup page header, next to the installed version. On request only, the browser asks GitHub for the published releases and says whether a newer one exists, with links to its release notes and to the update steps for UGOS Docker. A beta follows every release; a stable version follows stable releases only. The NAS sends nothing and the setup container opens no new connection; the page's content security policy allows only `api.github.com` besides the NAS itself. The page never updates the project.
- Stopping or updating the project no longer logs `MQTT connection lost` as a warning; an intentional stop now logs `Disconnected from MQTT broker`.

## 0.3.0b2 — 2026-11-15

Fresher data after restarts and clearer behavior when the broker is slow. No configuration changes are needed, and existing Home Assistant entities keep their identifiers.

- After a start or restart, HDD and volume readings are published as soon as the reader's first sample arrives, usually within a few minutes. Before, they stayed unavailable in Home Assistant until the next storage interval, 15 minutes by default. A disk that wakes from standby is also published at its next sample instead of waiting for the interval.
- New **HDD last reading** sensor in the HDD group: the time of the latest sample that read at least one HDD. It keeps that time while every disk sleeps, so Home Assistant can tell a recent temperature from an old one. It is a new entity on the same device; existing entities are unchanged.
- A broker that is slow to acknowledge no longer produces `MQTT publication failed` errors and repeated publications. Each batch is queued at once and waits at most 10 seconds in total; unacknowledged messages stay queued in the MQTT client and are delivered when the broker responds. The log shows one warning per episode and one line when the broker acknowledges again.

## 0.3.0b1 — 2026-11-15

First public beta. The container image is published on GitHub Container Registry for amd64 and arm64, and the UGOS Docker project follows its `beta` tag.

- One UGOS Docker project with two services from the same image: `setup`, which serves the browser wizard and publishes to MQTT without disk access, and `reader`, which reads SMART data and volume space without network access.
- Browser wizard with a setup token from the container log, light and dark themes, disk and volume discovery that does not read SMART, a dedicated MQTT login whose password stays on the NAS, and a separate interval for each reading group.
- SMART readings through the SAT path with only `CAP_SYS_RAWIO` on the reader, skipping sleeping disks. Disk and volume samples are scheduled separately, so frequent volume updates do not increase SMART polling.
- Reader targets and samples live in a RAM-backed volume, so routine samples are not written to the NAS storage pool.
- HDD sensor identifiers derive from the disk's hardware path and stay stable when Linux names the disks in a different order. `/volume1` is labelled `data`.
- Home Assistant MQTT Discovery for temperatures, CPU, memory, uptime, volume usage, and opt-in HDD SMART diagnostics.
- Setup responses carry an `X-Telemetry-Version` header, and the wizard shows the installed version.
- Tested on a DXP4800 Pro through NAS, broker and Home Assistant restarts, and a code upgrade and rollback. Other models, a public image update, and configuration migrations remain unverified.

Future releases should list user-visible changes, migration steps, verified hardware, and any known regressions here and in the GitHub Release notes.
