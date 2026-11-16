# Releases and updates

## Published images

Each GitHub Release runs the [publishing workflow](../.github/workflows/publish-image.yml). It checks that the release tag matches the package version, runs the tests, and publishes amd64 and arm64 images to GitHub Container Registry as `ghcr.io/interstellar0verdrive/ugreen-telemetry-mqtt`. Every image gets its version tag, such as `v0.3.0b1`. Every release, including a beta, also moves the `beta` tag; only a stable release moves `stable`.

[`compose.ugos.ghcr.yaml`](../compose.ugos.ghcr.yaml) follows `beta`. Once a stable release exists, you can switch both services to `stable` to receive only stable versions, or pin an exact version tag to stay on it.

You always start an update; the project never updates itself. The configuration and MQTT password volumes keep their contents across an update.

## Updating in UGOS

1. **Wait for the notice.** Press **Check for updates** on the setup page to see whether a newer release exists. When a release moves the tag you follow, UGOS Docker marks the project and its containers as **Updatable**, and the **Project** page shows a banner such as "1 project can be updated". The check is not immediate: on my NAS the notice appeared about two and a half hours after the release, and for one container before the other.
2. **Read the release notes**, then choose **Updatable** on the project, or **Update** in the banner, and confirm. UGOS pulls the image again under the same tag and recreates the project's containers with the same Compose configuration. Its warning that data not mounted to the NAS might be lost does not apply to the settings and the MQTT password, which live in named volumes. The reader rebuilds the in-memory snapshot by itself.
3. **Check the version** in the badge at the top of the setup page. If it still shows the previous version, open the project's **Compose configuration**, choose **Redeploy**, tick **Pull the latest image**, and deploy. This recreates both containers with the new image.

During the update, Home Assistant shows the NAS as unavailable for a few seconds. On my NAS, with 0.3.0b2, the HDD readings came back 67 seconds after the restart.

**Remove `build:` lines.** UGOS treats a service that still has a `build:` line as a locally built image: it never marks that service as updatable, and the project update leaves it on the old image. [`compose.ugos.ghcr.yaml`](../compose.ugos.ghcr.yaml) has none. If you moved a project from a source build to the published image, delete `build: .` and `pull_policy: never` from both services.

**Go back to a previous version** by replacing `beta` with an exact version tag, such as `v0.3.0b1`, in both services and redeploying the project with **Pull the latest image** ticked, because the older image may no longer be on the NAS. Readings added by the newer version then become unavailable in Home Assistant. To return, put `beta` back and redeploy the same way.

## What has been verified

On my DXP4800 Pro:
- a code upgrade from `0.3.0.dev1` to `0.3.0.dev2` and a rollback with source builds kept the saved settings, the masked MQTT password, and the same Home Assistant device and entities;
- moving the project from a source build to the published `beta` image kept them too;
- the update from `0.3.0b1` to `0.3.0b2` through the UGOS notice kept them, and added the new HDD last reading entity. In that update the project update recreated only the reader, because the setup service still had `build: .`; a redeploy with **Pull the latest image** completed it;
- a rollback from `0.3.0b2` to `v0.3.0b1` and the return to `beta` kept them too. On `v0.3.0b1` the HDD last reading entity was unavailable, as expected, and after the return it came back with the HDD readings 65 seconds after the restart.

Not verified yet: a project update in which UGOS recreates both containers on its own.

A new image cannot migrate incompatible settings by itself. Future code changes must keep the stored configuration format or ship an explicit migration, and the release notes must say so. Avoid automatic image updates: always read the release notes before updating.

The Compose files grant `SYS_RAWIO` only to the network-isolated reader, alongside its restricted SATA device access. The setup and MQTT service has no disk devices or raw I/O capability. This permission was needed for the SAT access path on the tested DXP4800 Pro and must be reviewed for each supported hardware layout.

## Building from source

[`compose.ugos.yaml`](../compose.ugos.yaml) builds the image on the NAS from a copy of this repository. It is useful for testing changes, but UGOS has no remote image tag to watch, so it cannot show an "update available" notice. To update, replace the source files and rebuild the project.

## Update check in the setup page

The setup page shows the installed version in its header, with a **Check for updates** button next to it. The check runs only when you press the button:

- your browser asks the GitHub API for the published releases; the NAS sends nothing, and the setup container opens no connection. The page's content security policy allows only `api.github.com` besides the NAS itself;
- a beta or release candidate is compared with every release, and a stable version with stable releases only;
- when a newer release exists, the page names it and links to its release notes and to the steps above. Otherwise it says you have the latest version, or that GitHub could not be reached.

The page never updates the project and has no access to the Docker socket: you always update from UGOS Docker.

## Release format

For each version, publish a GitHub Release with:

- a human-written changelog, verified NAS models and UGOS versions, and breaking changes;
- the source archive GitHub provides for the tag;
- the container image built by the workflow from that tag.

Version numbers follow Python's format: `0.3.0b1` is the first beta of 0.3.0, and its tag is `v0.3.0b1`. Betas are marked as pre-releases on GitHub. GitHub users can watch **Releases** to receive release notifications.

## Before a stable release

1. **Done on the tested DXP4800 Pro:** NAS, Mosquitto add-on, and Home Assistant Core restarts recovered publication on the same device. This does not validate a Home Assistant OS reboot.
2. Measure disk standby behavior with suspension enabled on at least one representative setup; do not generalize one model's result to all controllers.
3. Install from the published image on a NAS, and update between two published images through the UGOS update control, including a rollback. **Partly done:** the update from `0.3.0b1` to `0.3.0b2` through the UGOS notice, a rollback to `v0.3.0b1` and the return to `beta` worked on my DXP4800 Pro; a fresh installation and a project update that recreates both containers on its own remain. Repeat with a substantive configuration change when one exists, and ideally on a second NAS model.
4. Verify dedicated broker ACLs if they are described as a security boundary, and check that published images contain no secrets or disk serials.
5. Smoke-test the published amd64 and arm64 images, and document exactly which hardware was tested.
6. **Done on November 15, 2026:** private vulnerability reporting is enabled from the repository's Security tab, as described in [SECURITY.md](../SECURITY.md).

It is reasonable to keep the repository public but low-profile while collecting more operating time and compatibility reports. Community posts or a project listing can wait until the reboot, update, and standby claims have real evidence. If shared, ask for redacted model/firmware and sensor-availability reports, not credentials or full SMART dumps.
