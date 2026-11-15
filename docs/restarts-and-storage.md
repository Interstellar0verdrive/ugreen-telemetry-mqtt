# Restarts, persistence, and Home Assistant storage

## Restart sequence

Both containers use `restart: unless-stopped`: Docker starts them again after a normal daemon or NAS restart, except when someone deliberately stopped them. The configuration and MQTT password are kept in named volumes. The reader's targets and latest snapshot live in a RAM-backed volume, which `setup` rebuilds from the saved configuration after each start. HDD and volume readings return with the reader's next sample; samples missed while the NAS was off are not replayed.

The publisher reconnects to a broker that becomes available later. It sends retained MQTT Discovery configurations, current values, and availability. Home Assistant can rediscover the device after its own restart from those retained configurations, provided the broker retains them. A value can briefly be unavailable while the NAS, broker, and Home Assistant reconnect, and a brief broker stall can make a single publication time out before the publisher catches up.

On the tested DXP4800 Pro, both containers came back on their own after NAS reboots and power cycles, and fresh publication resumed after separate Mosquitto add-on and Home Assistant Core restarts, always on the same Home Assistant device. A code upgrade and rollback kept the settings and the device. A public image update and a configuration migration remain untested.

MQTT retained messages hold the latest value or configuration per topic; they are not a historical sample database. Old Discovery topics can remain retained after a reading group is disabled or a disk is removed, and each publisher session leaves a retained status topic. A cleanup mechanism is planned before a public release.

## Home Assistant Recorder

Home Assistant Recorder saves changed states in a database. With default settings, detailed states and five-minute short-term statistics are kept for 10 days, and eligible hourly long-term statistics are not automatically purged. The configured `state_class` makes this project's numeric sensors eligible for long-term statistics. Home Assistant filters repeated MQTT values that do not change the state; this project does not set `force_update`.

On the tested configuration, two active sensors report every 60 seconds (CPU usage and memory usage), and ten active sensors report every 15 minutes (CPU temperature, NVMe temperature, five HDD temperatures including maximum, two volume readings, and uptime). That is at most `2 × 1,440 + 10 × 96 = 3,840` **state publications per day**. It is an upper bound for Recorder changes, not a prediction of database size. If all 12 sensors generate long-term statistics, the hourly aggregates add at most about 288 rows per day, or about 105,000 per year. Actual storage depends on changed values, database backend, indexes, and your Recorder settings.

If you do not want history for a particular sensor, add its exact entity ID under Recorder's `exclude.entities` in Home Assistant's `configuration.yaml`. This leaves the current sensor value available but stops future history and statistics for that entity. Existing long-term statistics are not removed automatically by a later exclusion. Check your own Recorder configuration before assuming its 10-day default.

Official references: [Recorder](https://www.home-assistant.io/integrations/recorder/), [long-term statistics](https://www.home-assistant.io/docs/configuration/long-term-statistics/), [MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/), and [MQTT sensor options](https://www.home-assistant.io/integrations/sensor.mqtt/).
