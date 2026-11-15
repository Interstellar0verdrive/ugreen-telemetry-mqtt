# Security policy

The project reads SMART through a root container without network access and publishes selected telemetry through a separate, unprivileged container. The setup page stores a dedicated MQTT user's password on the NAS. Never include a password, secret file, serial number, or full SMART dump in an issue or pull request.

## Reporting a vulnerability

Report security problems privately through GitHub: open the [Security tab](https://github.com/Interstellar0verdrive/ugreen-telemetry-mqtt/security) of this repository and choose **Report a vulnerability**. Only I can read the report. Please don't post exploitable details in a public issue.

This is an experimental personal project: I read every report, but there is no promised support window or response time yet.

The [security model](docs/security-model.md) describes the trust boundaries and what leaves the NAS.

The project is an unreleased prototype. Its setup page uses local HTTP, so the setup token and MQTT password must be used only on a trusted LAN. The reader's device access is still under NAS-side validation.
