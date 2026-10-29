# Measuring monitoring impact

HDD diagnostic sensors such as `start_stop_count` and `load_cycle_count` come from SMART attributes 4 and 193 when a drive exposes them under the expected names. They are cumulative counters, not temperature readings or reliable estimates of remaining life. The helper reads them in the same SMART call as temperature, so they do not add disk polls.

1. Enable the diagnostic entities in Home Assistant if you want to compare counters. If a counter is missing, first check whether that HDD exposes the attribute; missing does not mean zero.
2. Record each disk's starting values and compare the increase after 24–48 hours of normal use. Compare changes, not absolute values. A rise close to 96 starts per day per disk deserves investigation because the timer runs 96 times daily, but correlation alone does not identify the cause.
3. If the increase looks suspicious, compare with a similar period after intentionally pausing the snapshot timer. First confirm that any automations using HDD temperature tolerate unavailable data. Restart the timer after the comparison.
4. To inspect load, compare container resource use, UGOS I/O graphs, and service errors during similar workloads. The publisher has a 128 MiB memory limit and cannot write to data volumes. NAS-wide CPU and memory usage include unrelated work.

On some controllers, even `smartctl -n standby,0` may wake a drive. Measure the behavior on the exact NAS and disk combination before claiming standby-safe monitoring.

## Initial DXP4800 Pro observation

In an approximately eight-hour overnight trial, the four HDDs' Start/Stop and Load Cycle counters did not increase. UGOS disk suspension was disabled during that trial. The observation confirms that telemetry ran, but it does **not** establish what happens with disk suspension enabled. The original values are kept in a private trial log outside the public repository.
