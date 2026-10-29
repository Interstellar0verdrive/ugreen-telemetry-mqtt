# UGOS Docker setup UI prototype

This is development code. It has not replaced the tested SSH installer. A private two-container pilot has run against the real broker; fresh installation and public-release update behavior still need validation before this becomes a supported release.

The screens below are light- and dark-mode mockups based on the current wizard. They contain no setup token, broker credentials, or disk serial numbers. The chosen disks and intervals mirror the tested DXP4800 Pro pilot, not settings to copy to another NAS.

## Intended user journey

1. In UGOS Docker, create one **project** from a short Compose file that points at a tagged GHCR image.
2. Open `http://NAS-IP:8765` on the trusted LAN. In the UGOS Docker project, select the `setup` container and copy the setup token from its Logs tab. The `reader` container has a separate log.

   <p align="center">
     <img src="images/token-preview-light.svg#gh-light-mode-only" width="100%" alt="Light-mode mockup of the setup-token screen, with an empty token field">
     <img src="images/token-preview-dark.svg#gh-dark-mode-only" width="100%" alt="Dark-mode mockup of the setup-token screen, with an empty token field">
   </p>

3. The wizard lists SATA disks by Linux name and shows their HDD/SSD type. Compare the names with UGOS Storage, select the disks and volumes, then enter a dedicated MQTT login and choose reading groups.

   <p align="center">
     <img src="images/storage-preview-light.svg#gh-light-mode-only" width="100%" alt="Light-mode mockup of the selected disks and volume">
     <img src="images/storage-preview-dark.svg#gh-dark-mode-only" width="100%" alt="Dark-mode mockup of the selected disks and volume">
   </p>

   <p align="center">
     <img src="images/readme-preview-light.svg#gh-light-mode-only" width="100%" alt="Light-mode mockup of the reading groups and intervals">
     <img src="images/readme-preview-dark.svg#gh-dark-mode-only" width="100%" alt="Dark-mode mockup of the reading groups and intervals">
   </p>

4. Save. Each reading uses the selected update interval. The isolated reader schedules SMART checks separately from volume-space checks; SMART intervals have a five-minute minimum. The unprivileged service publishes standard MQTT state topics and Home Assistant MQTT Discovery.
5. For a later release, review its changelog and use the project's image update control in UGOS. The configuration and MQTT password volumes retain their contents across image replacement. The temporary reader targets and samples are rebuilt after a restart.

The UI uses local HTTP, so the setup token and MQTT password travel unencrypted across the LAN during setup. Limit the published port to a trusted network. Do not expose it through a router or reverse proxy without a proper HTTPS and access-control setup.

## Why the project has two containers

Docker fixes device access when a container starts. A wizard cannot discover a disk and grant itself access to that disk later without the Docker control socket or broad initial device access. The reader therefore has device access from the start, but no network, MQTT password, or web port. The setup and MQTT container has network access and the MQTT password, but no disk devices. Both services use the same image and are managed as one UGOS Docker project.

The reader sees the host `/dev` directory read-only, has a device cgroup rule for read access to SATA block major 8, and receives `CAP_SYS_RAWIO` for the tested SAT path. This is broader than mapping one named disk and still needs NAS-side validation. A read-only device mapping is not a guarantee that every possible device command is harmless. The reader uses only allowlisted `/dev/sd*` paths selected in the wizard and runs `smartctl -d sat -n standby,0 -A` without `--allow-wake`.

Disabling HDD, SATA SSD, or volume readings also removes those targets from the reader's next sample. Disabling HDD diagnostics alone keeps the HDD temperature sample and simply omits the counters from MQTT.

The example Compose file keeps configuration and secrets in persistent Docker volumes. It shares reader targets and telemetry samples through a small `tmpfs` volume, so routine sample writes do not go to the NAS's Docker storage pool. On startup, the setup service recreates the reader targets from saved configuration. A reboot clears the temporary samples; fresh storage values appear after the reader samples again. This does not prove that other NAS services, filesystem-space queries, Docker logs, or SMART requests leave sleeping disks undisturbed.

## Current prototype limits

- Only `/volume1` is mounted for filesystem-space readings in the example Compose file. Other mounted data volumes require adding matching read-only mounts to the reader and listing them in `AVAILABLE_VOLUME_PATHS` on the setup service.
- The reviewed wizard and per-reading interval controls passed local tests and browser review with dummy data. On October 26, 2026 the isolated NAS project was rebuilt with image `ui-reviewed-dev1`; the authenticated wizard showed its prior saved settings, and the internal broker accepted fresh state topics for four HDD temperatures, the selected volume, CPU, and memory. Exact values were not visible in the UGOS broker log.
- The development Compose file uses a local build and does not provide an UGOS update badge. Private GHCR `v0.3.0.dev1` and `v0.3.0.dev2` images were pulled and switched in the existing pilot, then it was restored to the local image. The release template and image-publishing workflow have not been exercised with a public image or an UGOS update badge.
- Setup changes restart the MQTT publisher. Home Assistant may retain old MQTT Discovery entities after a sensor group is disabled; cleanup of stale discovery entries is not implemented yet.
- There is no setup-page TLS. The page is intended for a trusted LAN only.
- Two one-shot UGOS probes reached `/dev/sda`, first through a dynamic read-only `/dev` mount and then through Docker's explicit read-only device mapping. Both granted `CAP_SYS_RAWIO`; the second verified it was effective in the process. Both still got `EACCES` on the ATA power-mode ioctl. The NAS runs Linux 6.18.15, whose ATA ioctl path requires both `CAP_SYS_ADMIN` and `CAP_SYS_RAWIO`. The SLEEP response masks that denial and does not establish the disk's power state. A third one-shot probe used the SAT path with only `CAP_SYS_RAWIO`; the power-mode check succeeded and SMART attributes 190 and 194 reported 45 C on one active HDD. This validates SAT on that device, but not the full reader, sleeping-disk behavior, or other models. The web process must not inherit raw I/O capability in a releasable design.
- The setup page was exercised locally with dummy credentials. Token access, saving, and separation of the MQTT password from the configuration files worked. In UGOS, a first two-service trial built but did not start because it tried to pull a local image. A second trial started and served the login page; its reader could not traverse the shared config volume. After correcting the image and Compose file, a third trial started both containers, unlocked the wizard, discovered the four SATA HDDs and `/volume1`, saved a dummy loopback MQTT configuration, and wrote an empty snapshot. Selecting one HDD and `/volume1` produced a volume reading but no HDD reading. The third project was stopped and restarted once; its saved settings and selections survived, then it was stopped again.
- A separate three-service trial added an internal Mosquitto broker with no host MQTT port or real credentials. The wizard retained its dummy configuration across an image rebuild. The publisher sent retained CPU and volume states to that broker. A startup race initially delayed the first volume state; the publisher now checks for a newly written snapshot and published the volume value promptly in the rebuilt image. The isolated project was stopped after verification. Home Assistant and the real broker were not involved.
- The isolated NAS image used for the first trial checked snapshot-file metadata once a second. The next image checks snapshot and target-file metadata at most once a minute; the setup process reacts directly to a wizard save. UGOS rebuilt that image and an internal broker received a retained volume value. New storage selections or samples can take up to about two minutes to reach MQTT.
- A read-only filesystem check in the isolated reader showed that Docker's named volumes for configuration and snapshots were on `/volume1`, the HDD data pool. The next revision moved temporary targets and samples into a shared memory-backed volume and suppressed routine success logs. UGOS rebuilt both project containers with this revision. In the reader, `df -T` reported `tmpfs` for `/snapshots` and Btrfs for `/host/volume1`; both temporary files existed after restart, and the internal MQTT broker returned the retained volume-used value. During a later active-disk trial, all four HDDs showed thousands of reads in ten seconds, but the container reported zero HDD samples. `smartctl -r ioctl,1` showed `CHECK POWER MODE returned -1 errno=13 [Permission denied]`; its SLEEP message was not a real power-state measurement. Device-access permissions need correction before a disk-standby or active-SMART claim.
- An approved SAT revision gave only the reader `CAP_SYS_RAWIO` and kept it without network or MQTT credentials. The reader then produced temperatures and Start/Stop and Load Cycle counters for all four active HDDs. The test still cannot establish behavior while an HDD is genuinely in standby. The host-based telemetry was later stopped reversibly so the SAT reader could be observed without a second project polling SMART.
- The source normalizes sysfs paths before deriving HDD IDs and labels `/volume1` as `data` in the wizard. Both changes are in the October 26 isolated image. A read-only comparison with the historical Home Assistant MQTT registry confirmed all four HDD IDs (`sda`–`sdd`) and the `data` volume label. The isolated project uses NAS ID `ugreen-isolated-test`; the historical device uses `dxp4800pro`. Set the latter in a real-broker pilot to preserve entity identity, then re-enable the existing Home Assistant device after confirming MQTT publication.
- A separate two-container pilot connected to the real broker on October 27, 2026. Its settings and historical Home Assistant device survived separate NAS, broker add-on, and Home Assistant Core restarts, plus a small local `0.3.0.dev1` → `0.3.0.dev2` code upgrade and rollback. A later private GHCR `dev1` → `dev2` → `dev1` image switch and return to the local image also retained settings and device identity. Fresh install by another user, a public image update, configuration migrations, two-bay NAS layouts, and compatibility with other UGREEN models remain unverified. A scheduled reader sample while disks were in standby was not directly observed.

## Source layout

- `compose.ugos.yaml`: development project with setup and reader services.
- `src/ugreen_telemetry/web.py` and `web_assets/`: wizard and MQTT process supervision.
- `src/ugreen_telemetry/reader.py` and `host-smart-snapshot.py`: isolated SMART sampler.
- `src/ugreen_telemetry/main.py`, `sensors.py`, `mqtt.py`: MQTT Discovery publisher.

Never include an MQTT password, setup token, full SMART dump, serial number, or private path in a bug report.
