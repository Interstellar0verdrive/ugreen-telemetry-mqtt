# Restarts, persistence, and Home Assistant storage

## Restart sequence

The installer enables `ugreen-telemetry-snapshot.timer` at boot. The timer runs every quarter-hour and has `Persistent=false`, so it does not replay all readings missed while the NAS was off. Docker Compose sets `restart: unless-stopped` for the MQTT publisher: Docker restarts it after a normal daemon/NAS restart, except when someone deliberately stopped the container.

The publisher reconnects to a broker that becomes available later. It sends retained MQTT Discovery configurations, current values, and availability. Home Assistant can rediscover the device after its own restart from those retained configurations, provided the broker retains them. A value can briefly be unavailable while the NAS, broker, and Home Assistant reconnect. After a long NAS shutdown, HDD and volume readings need both a fresh host snapshot and the publisher's next 15-minute poll. This host-installer path has not been tested through a whole-NAS reboot.

The separate two-container UGOS browser pilot was tested through a NAS reboot on October 27, 2026. Both containers returned without manual start; its RAM-backed snapshot was recreated and all four HDD temperature entities became available again on the same Home Assistant device. Separate Mosquitto add-on and Home Assistant Core restarts also recovered fresh publication on that device. Image replacement and rollback remain untested.

MQTT retained messages hold the latest value or configuration per topic; they are not a historical sample database. Old discovery topics and per-process status topics can remain retained after changes or repeated publisher restarts. A cleanup mechanism is planned before a public release.

## Home Assistant Recorder

Home Assistant Recorder saves changed states in a database. With default settings, detailed states and five-minute short-term statistics are kept for 10 days, and eligible hourly long-term statistics are not automatically purged. The configured `state_class` makes this project's numeric sensors eligible for long-term statistics. Home Assistant filters repeated MQTT values that do not change the state; this project does not set `force_update`.

On the tested configuration, two active sensors report every 60 seconds (CPU usage and memory usage), and ten active sensors report every 15 minutes (CPU temperature, NVMe temperature, five HDD temperatures including maximum, two volume readings, and uptime). That is at most `2 × 1,440 + 10 × 96 = 3,840` **state publications per day**. It is an upper bound for Recorder changes, not a prediction of database size. If all 12 sensors generate long-term statistics, the hourly aggregates add at most about 288 rows per day, or about 105,000 per year. Actual storage depends on changed values, database backend, indexes, and your Recorder settings.

If you do not want history for a particular sensor, add its exact entity ID under Recorder's `exclude.entities` in Home Assistant's `configuration.yaml`. This leaves the current sensor value available but stops future history and statistics for that entity. Existing long-term statistics are not removed automatically by a later exclusion. Check your own Recorder configuration before assuming its 10-day default.

Official references: [Recorder](https://www.home-assistant.io/integrations/recorder/), [long-term statistics](https://www.home-assistant.io/docs/configuration/long-term-statistics/), [MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/), and [MQTT sensor options](https://www.home-assistant.io/integrations/sensor.mqtt/).
