# Measuring monitoring impact

HDD diagnostic sensors such as `start_stop_count` and `load_cycle_count` come from SMART attributes 4 and 193 when a drive exposes them under the expected names. They are cumulative counters, not temperature readings or reliable estimates of remaining life. The reader gets them in the same SMART call as temperature, so they do not add disk polls.

1. Enable the HDD diagnostics group in the wizard and the diagnostic entities in Home Assistant if you want to compare counters. If a counter is missing, first check whether that HDD exposes the attribute; missing does not mean zero.
2. Record each disk's starting values and compare the increase after 24–48 hours of normal use. Compare changes, not absolute values. With the default 15-minute interval, the reader checks each selected disk 96 times a day; a rise in Start/Stop count close to that number deserves investigation, but correlation alone does not identify the cause.
3. If the increase looks suspicious, compare with a similar period with HDD readings turned off in the wizard, or with the `reader` container stopped. First confirm that any automations using HDD temperature tolerate unavailable data. Turn the readings back on after the comparison.
4. To inspect load, compare container resource use, UGOS I/O graphs, and container errors during similar workloads. The reader is limited to 128 MiB of memory and the setup service to 192 MiB; neither can write to data volumes. NAS-wide CPU and memory usage include unrelated work.

On some controllers, even `smartctl -n standby,0` may wake a drive. Measure the behavior on the exact NAS and disk combination before claiming standby-safe monitoring.

## DXP4800 Pro observation

With UGOS disk suspension enabled, all four HDDs were seen to sleep for long periods while the reader was running. Some wake-ups had other or unknown causes, and a scheduled reader sample taken during standby was not directly observed. The reader was not shown to keep the disks awake on that NAS, but this does not prove that every sample is standby-safe.

When the reader skips a sleeping disk, that disk's readings are marked unavailable until its next successful sample, and the maximum HDD temperature is not published for that sample. In Home Assistant, a sensor's last-updated time changes only when its value changes, so it does not show by itself how recent an HDD value is.
