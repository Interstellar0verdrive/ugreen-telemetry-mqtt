# Releases and updates

## Published images

Each GitHub Release runs the [publishing workflow](../.github/workflows/publish-image.yml). It checks that the release tag matches the package version, runs the tests, and publishes amd64 and arm64 images to GitHub Container Registry as `ghcr.io/interstellar0verdrive/ugreen-telemetry-mqtt`. Every image gets its version tag, such as `v0.3.0b1`. Every release, including a beta, also moves the `beta` tag; only a stable release moves `stable`.

[`compose.ugos.ghcr.yaml`](../compose.ugos.ghcr.yaml) follows `beta`. Once a stable release exists, you can switch both services to `stable` to receive only stable versions, or pin an exact version tag to stay on it.

When a newer image is published under the tag you follow, UGOS Docker can show that an update is available. Read the release notes, then update the image and redeploy the project in UGOS. You always start the update; the project never updates itself. The configuration and MQTT password volumes keep their contents across the update.

The update control in UGOS and an update between two published images have not been verified end to end yet. On the tested DXP4800 Pro, a code upgrade from `0.3.0.dev1` to `0.3.0.dev2` and a rollback with source builds kept the saved settings, the masked MQTT password, and the same Home Assistant device and entities.

A new image cannot migrate incompatible settings by itself. Future code changes must keep the stored configuration format or ship an explicit migration, and the release notes must say so. Avoid automatic image updates until restart and rollback behavior has been tested with published images.

The Compose files grant `SYS_RAWIO` only to the network-isolated reader, alongside its restricted SATA device access. The setup and MQTT service has no disk devices or raw I/O capability. This permission was needed for the SAT access path on the tested DXP4800 Pro and must be reviewed for each supported hardware layout.

## Building from source

[`compose.ugos.yaml`](../compose.ugos.yaml) builds the image on the NAS from a copy of this repository. It is useful for testing changes, but UGOS has no remote image tag to watch, so it cannot show an "update available" notice. To update, replace the source files and rebuild the project.

## Planned: update check in the wizard

The setup page should offer an on-demand **Check for updates** control. It should show the installed version, check the latest release, and link to its release notes. If the check fails or the NAS is offline, it should say that the result is unavailable. It should direct the user to update the image in UGOS Docker; the setup page must not access the Docker socket or perform the update itself.

## Release format

For each version, publish a GitHub Release with:

- a human-written changelog, verified NAS models and UGOS versions, and breaking changes;
- the source archive GitHub provides for the tag;
- the container image built by the workflow from that tag.

Version numbers follow Python's format: `0.3.0b1` is the first beta of 0.3.0, and its tag is `v0.3.0b1`. Betas are marked as pre-releases on GitHub. GitHub users can watch **Releases** to receive release notifications.

## Before a stable release

1. **Done on the tested DXP4800 Pro:** NAS, Mosquitto add-on, and Home Assistant Core restarts recovered publication on the same device. This does not validate a Home Assistant OS reboot.
2. Measure disk standby behavior with suspension enabled on at least one representative setup; do not generalize one model's result to all controllers.
3. Install from the published image on a NAS, and update between two published images through the UGOS update control, including a rollback. Repeat with a substantive configuration change when one exists, and ideally on a second NAS model.
4. Verify dedicated broker ACLs if they are described as a security boundary, and check that published images contain no secrets or disk serials.
5. Smoke-test the published amd64 and arm64 images, and document exactly which hardware was tested.
6. **Done on November 15, 2026:** private vulnerability reporting is enabled from the repository's Security tab, as described in [SECURITY.md](../SECURITY.md).

It is reasonable to keep the repository public but low-profile while collecting more operating time and compatibility reports. Community posts or a project listing can wait until the reboot, update, and standby claims have real evidence. If shared, ask for redacted model/firmware and sensor-availability reports, not credentials or full SMART dumps.
