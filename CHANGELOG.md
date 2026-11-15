# Changelog

All notable changes will be documented here. This project has not made a public release yet.

## Unreleased

- One UGOS Docker project with two services from the same image: `setup`, which serves the browser wizard and publishes to MQTT without disk access, and `reader`, which reads SMART data and volume space without network access.
- Browser wizard with a setup token from the container log, light and dark themes, disk and volume discovery that does not read SMART, a dedicated MQTT login whose password stays on the NAS, and a separate interval for each reading group.
- SMART readings through the SAT path with only `CAP_SYS_RAWIO` on the reader, skipping sleeping disks. Disk and volume samples are scheduled separately, so frequent volume updates do not increase SMART polling.
- Reader targets and samples live in a RAM-backed volume, so routine samples are not written to the NAS storage pool.
- HDD sensor identifiers derive from the disk's hardware path and stay stable when Linux names the disks in a different order. `/volume1` is labelled `data`.
- Home Assistant MQTT Discovery for temperatures, CPU, memory, uptime, volume usage, and opt-in HDD SMART diagnostics.
- Development build `0.3.0.dev2` adds an `X-Telemetry-Version` header to setup responses; its configuration format and sensor behavior match `0.3.0.dev1`.
- Tested on a DXP4800 Pro through NAS, broker and Home Assistant restarts, and a code upgrade and rollback. Other models, a public image update, and configuration migrations remain unverified.

Future releases should list user-visible changes, migration steps, verified hardware, and any known regressions here and in the GitHub Release notes.
