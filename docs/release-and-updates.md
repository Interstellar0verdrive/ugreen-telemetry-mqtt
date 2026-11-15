# Releases and updates

## Today: build from source

No public container image has been published yet. The [installation guide](installation.md) builds the image on the NAS from [`compose.ugos.yaml`](../compose.ugos.yaml). This works, but UGOS Docker has no remote image tag to watch, so it cannot show an "update available" notice. To update, replace the source files and rebuild the project; the configuration and MQTT password volumes keep their contents across the rebuild. On the tested DXP4800 Pro, a code upgrade from `0.3.0.dev1` to `0.3.0.dev2` and a rollback kept the saved settings, the masked MQTT password, and the same Home Assistant device and entities.

## Planned: published images

The [GitHub Actions workflow](../.github/workflows/publish-image.yml) checks that the GitHub Release tag matches the package version, runs tests, and publishes amd64 and arm64 images to GitHub Container Registry. Every release receives a version tag; only a non-prerelease also moves `stable`. The template [`compose.ugos.ghcr.example.yaml`](../compose.ugos.ghcr.example.yaml) points both services at that image; its image name is still a placeholder until the first public release.

A user who chooses `:stable` can read the release notes and then use UGOS's image update control when UGOS detects the new image. The user always starts the update; the project never updates itself. This flow has not been verified end to end with a public image yet.

A tagged image update cannot itself migrate incompatible settings. Future code changes must keep the stored configuration format or ship an explicit migration, and the release notes must say so. Avoid automatic image updates until restart and rollback behavior has been tested with a published image.

The template grants `SYS_RAWIO` only to the network-isolated reader, alongside its restricted SATA device access. The setup and MQTT service has no disk devices or raw I/O capability. This permission was needed for the SAT access path on the tested DXP4800 Pro and must be reviewed for each supported hardware layout.

## Planned: update check in the wizard

Once a public release exists, the setup page should offer an on-demand **Check for updates** control. It should show the installed version, check the latest stable release, and link to its release notes. If the check fails or the NAS is offline, it should say that the result is unavailable. It should direct the user to update the image in UGOS Docker; the setup page must not access the Docker socket or perform the update itself. Test this flow against an actual published release before describing it as supported.

## Release format

For each tagged version, publish a GitHub Release with:

- a human-written changelog, verified NAS models and UGOS versions, and breaking changes;
- the source archive GitHub provides for the tag;
- a container image tagged with the release version; non-prereleases also update `stable` after tests pass.

GitHub users can watch **Releases** to receive release notifications.

## Before the first public release

1. **Done on the tested DXP4800 Pro:** NAS, Mosquitto add-on, and Home Assistant Core restarts recovered publication on the same device. This does not validate a Home Assistant OS reboot or a published image.
2. Measure disk standby behavior with suspension enabled on at least one representative setup; do not generalize one model's result to all controllers.
3. **Partly done:** a small code upgrade and rollback passed with a source build. Repeat with a substantive configuration change when one exists, test a public image update and the UGOS update control, and ideally test a second NAS model.
4. Replace the image placeholder in the GHCR template, publish the image, make the package public, and check that it can be pulled anonymously. Then do a fresh installation from it.
5. Verify dedicated broker ACLs if they are described as a security boundary, and check that published images contain no secrets or disk serials.
6. Build and smoke-test the supported CPU architectures, and document exactly which hardware was tested.
7. **Done on November 15, 2026:** private vulnerability reporting is enabled from the repository's Security tab, as described in [SECURITY.md](../SECURITY.md).

It is reasonable to keep the repository public but low-profile while collecting more operating time and compatibility reports. Community posts or a project listing can wait until the reboot, update, and standby claims have real evidence. If shared, ask for redacted model/firmware and sensor-availability reports, not credentials or full SMART dumps.
