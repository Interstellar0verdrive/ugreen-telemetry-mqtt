# Changelog

All notable changes will be documented here. This project has not made a public release yet.

## Unreleased

- A private two-service pilot published to the existing Home Assistant MQTT device on a DXP4800 Pro. Settings and sensor identity survived separate NAS, broker add-on, and Home Assistant Core restarts, plus a local upgrade between `0.3.0.dev1` and `0.3.0.dev2` and rollback. A registry-image update, configuration migration, and fresh installation by another user remain untested.
- Prepared development build `0.3.0.dev1` for the isolated UGOS project. Refined the token screen with a working show/hide control, clearer connection and authentication errors, and stable validation placement. Centered the selected-card check mark.
- Integrated the reviewed light/dark wizard design with real token access, inventory, configuration save, and responsive controls. Reading intervals are now validated and saved per group; the isolated reader schedules volume and disk samples separately so frequent volume updates do not increase SMART polling.
- Added a source-visible UGOS Docker project prototype with a browser-based setup page, persistent settings, and two isolated services. An isolated NAS project completed token login, disk discovery, settings persistence, volume reading, and SAT SMART sampling on four active HDDs. Its broker is internal to the test project. UGOS logged sustained HDD sleep while its reader ran, though a scheduled sample during standby was not directly observed.
- Kept HDD identifiers stable between host and container sysfs mount paths, and named `/volume1` as `data` in the UGOS wizard to preserve the existing Home Assistant sensor identity during migration.
- Moved CPU and SSD/NVMe temperature sampling to the 15-minute interval. CPU and memory usage remain on the one-minute interval.
- Matched the future GHCR Compose template's reader permissions to the tested SAT project and added a release-tag/package-version check to the image-publishing workflow.
- Documented the planned reversible migration from the host installer to the UGOS project.
- The setup page discovers SATA disk names and lets users choose MQTT and sensor groups without editing environment files.
- Guided first-time setup for selected SATA disks and mounted data volumes.
- Separate root-owned SMART snapshot helper and unprivileged MQTT publisher.
- Home Assistant MQTT Discovery for temperatures, CPU, memory, uptime, volume usage, and opt-in HDD SMART diagnostics.
- Tested on a DXP4800 Pro with UGOS Pro 1.20.0.0142; other models and full reboot recovery remain unverified.

Future releases should list user-visible changes, migration steps, verified hardware, and any known regressions here and in the GitHub Release notes.
