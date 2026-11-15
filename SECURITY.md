# Security policy

The project reads SMART as root on the NAS and publishes selected telemetry through a restricted container. The installer stores a dedicated MQTT user's password on the NAS. Never include a password, secret file, serial number, or full SMART dump in an issue or pull request.

## Reporting a vulnerability

Report security problems privately through GitHub: open the [Security tab](https://github.com/Interstellar0verdrive/ugreen-telemetry-mqtt/security) of this repository and choose **Report a vulnerability**. Only I can read the report. Please don't post exploitable details in a public issue.

This is an experimental personal project: I read every report, but there is no promised support window or response time yet.

The [security model](docs/security-model.md) describes the trust boundaries and what leaves the NAS.

The browser-based UGOS setup is a separate, unreleased prototype. Its local HTTP setup token and MQTT password must be used only on a trusted LAN. The root reader has no network and does not mount MQTT secrets; device access is still under NAS-side validation. See [prototype limits](docs/ugos-ui-prototype.md).
