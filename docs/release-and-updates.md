# Releases and updates

## Today: tested SSH installer

The guided installer handles a **fresh installation only** and refuses to overwrite its files or systemd units. The NAS-tested installation builds a local Docker image (`ugreen-telemetry-mqtt:local`) from the extracted source. UGOS Docker therefore has no remote image tag to watch, and it will not show a reliable "update available" notice for this project. Re-running the installer is not an update procedure. A local two-code-version upgrade and rollback passed for the browser pilot, but a supported upgrade path for the SSH installation and a published-image update remain untested.

## Planned UGOS Docker project

The browser setup path is one UGOS Docker project with two services, `setup` and `reader`, using the **same image**. Configuration and the MQTT password use persistent named Docker volumes. Reader targets and the latest snapshot use a separate memory-backed volume that is rebuilt after a restart. Replacing the image should preserve the persistent volumes. The source-visible [`compose.ugos.ghcr.example.yaml`](../compose.ugos.ghcr.example.yaml) is a future release template; its image name is deliberately a placeholder, and no public image has been published. The separate [`compose.ugos.yaml`](../compose.ugos.yaml) builds a local development image and has no registry update path.

An October 27, 2026 private pilot on the DXP4800 Pro retained settings and historical Home Assistant entity IDs through separate NAS, broker add-on, and Home Assistant Core restarts. A first controlled Compose image-tag change rebuilt both services from the same on-NAS source and recovered the existing device and all four HDD temperatures after upgrade and rollback ([pilot status](../../../work/ugos-ui-real-broker-pilot-status.md)). A second test rebuilt both services from genuinely different source code, upgrading `0.3.0.dev1` to `0.3.0.dev2` and then rolling back. The newer code changed the package version and added an HTTP version header. The wizard retained its saved settings and masked MQTT password; Home Assistant kept the same device and 38 entities, with CPU/memory publishing and all four HDD temperatures recovering after each redeploy ([code-version test status](../../../work/ugos-ui-code-upgrade-test-status.md)). This validates a small local code-version change, **not** a published image pull or configuration migration. The pilot uses a local development tag, so an UGOS image-update badge is not available. Never start the preserved old host publisher alongside the pilot because both use the same NAS ID.

The planned [GitHub Actions workflow](../.github/workflows/publish-image.yml) checks that the GitHub Release tag matches the package version, runs tests, and publishes amd64 and arm64 GHCR images. Every release receives a version tag; only a non-prerelease also moves `stable`. A user who chooses `:stable` can review the release notes and then use UGOS's image update control when UGOS detects the new image. The user must initiate the update. This behavior has not yet been verified end to end on the NAS, so the UI project is not advertised as a supported install path.

TODO: Add an on-demand **Check for updates** control to the setup page once a public GitHub release exists. Show the installed version, check the latest stable release, and link to its release notes. If the check fails or the NAS is offline, show that the result is unavailable. Direct the user to update the image in UGOS Docker; the setup page must not access the Docker socket or perform the update itself. Test this flow against an actual published release before describing it as supported.

Check that the GHCR package is public before inviting anonymous users to pull it. A tagged image update cannot itself migrate incompatible settings; future code changes must preserve the stored configuration format or ship an explicit migration. Avoid automatic image updates until restart and rollback behavior has been tested.

The release Compose template grants `SYS_RAWIO` only to the network-isolated reader, alongside its restricted SATA device access. The setup and MQTT service has no disk devices or raw I/O capability. This permission was needed for the SAT access path on the tested DXP4800 Pro and must be reviewed for each supported hardware layout.

## Intended release format

The GitHub repository should keep all Python source, Dockerfile, Compose files, systemd units, tests, and documentation in plain text. Do not commit generated `.pyz` files. For each tagged version, publish a GitHub Release with:

- a human-written changelog, supported/verified NAS and UGOS versions, and breaking changes;
- a `.pyz` installer built from that exact tag, plus its SHA-256 checksum;
- the source archive GitHub provides for the tag;
- a container image tagged with the release version; non-prereleases also update `stable` after tests pass.

A `.pyz` is itself a ZIP of readable files. Users can inspect the repository, compare the tag, or extract the archive before executing it. GitHub users can watch **Releases** to receive release notifications. The user initiates image updates in UGOS; the project does not silently update itself.

The repository's GitHub About text could be: "Experimental UGREEN NAS telemetry for Home Assistant via MQTT; NAS administrator credentials stay on the NAS." Keep the root small: README, changelog, license, contribution and security notes, installer and Compose files, with implementation under `src/`, validation under `tests/`, and detailed guides under `docs/`. The README should state the limited test coverage before installation instructions, so visitors can judge whether to try it.

## Upgrade path to implement before broad promotion

A future explicit upgrade command should check its version and prerequisites, back up the live configuration and MQTT secret locally, stage the new host helper and container image, validate both, replace the two components in a controlled order, and roll back if the health check fails. It must preserve chosen disks, volumes, NAS identity, MQTT settings, and Home Assistant entity IDs. The user should read release notes and initiate the upgrade; no automatic upgrade of a root-owned SMART reader is planned.

A guided uninstaller should separately remove only this project's timer, service, container, image, and private files. Retained MQTT discovery and Home Assistant history need an explicit, clearly documented choice because removing them can affect existing dashboards and automations.

## Before a public release

1. Run a real restart test for the NAS, broker, and Home Assistant. **Done for the private two-service pilot on October 27, 2026:** separate NAS, Mosquitto add-on, and Home Assistant Core restarts recovered the same device. This does not validate Home Assistant OS reboot or a future registry image.
2. Measure disk standby behavior with suspension enabled on at least one representative setup; do not generalize one model's result to all controllers.
3. **Done on the private DXP4800 Pro pilot:** a small local `0.3.0.dev1` → `0.3.0.dev2` code upgrade and rollback passed. Repeat with a substantive code or configuration migration when one exists, test an actual registry pull and update through UGOS, and ideally test a second NAS model.
4. Verify dedicated broker ACLs if they are described as a security boundary, and check that published artifacts contain no secrets or disk serials.
5. Build and smoke-test the supported CPU architectures. Publish checksums and document exactly which hardware was tested.
6. Enable a private security-reporting channel before inviting security reports.

It is reasonable to leave the repository public but low-profile while collecting more operating time and compatibility reports. Community posts or a project listing can wait until the reboot, update, and standby claims have real evidence. If shared, ask for redacted model/firmware and sensor-availability reports, not credentials or full SMART dumps.
