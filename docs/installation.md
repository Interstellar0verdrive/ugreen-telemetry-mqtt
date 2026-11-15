# Installation

This is an experimental guide. It has been followed on one DXP4800 Pro; other models still need real-world testing. The screenshots below show the real wizard running with example data, in your browser's light or dark theme. They contain no real token, broker credentials, or disk serial numbers, and the disks and intervals shown are an example, not settings to copy.

## Before you start

1. In Home Assistant, enable the MQTT integration and create a **dedicated broker login** for telemetry. Keep the broker address, port, username and password outside this repository.
2. Enable Docker in UGOS. The NAS needs Internet access to download the image, or to build it from source.
3. In UGOS Storage, note which SATA disks and data volumes you want to monitor. The wizard shows Linux names such as `/dev/sda`, and you must check that each one belongs to the intended pool. A USB disk may also have an `sd*` name.

## Create the UGOS Docker project

1. Create an empty folder on the NAS for the project, for example `/volume1/docker/ugreen-telemetry`.
2. In UGOS Docker, create a **project** in that folder and paste the contents of [`compose.ugos.ghcr.yaml`](../compose.ugos.ghcr.yaml) as its Compose file. UGOS downloads the published image from GitHub Container Registry and starts two services from it, `setup` and `reader`.
3. Check that both containers are running.

The Compose file follows the `beta` image tag, which every release moves, so UGOS can show when a newer image is available. To build the image yourself instead, copy this repository to the project folder and use [`compose.ugos.yaml`](../compose.ugos.yaml); UGOS then has no remote image to watch for updates.

Both Compose files mount only `/volume1` for volume-space readings. For another data volume, add a matching read-only mount to the `reader` service, such as `/volume2:/host/volume2:ro`, and list every mounted volume on the `setup` service with `AVAILABLE_VOLUME_PATHS: /volume1,/volume2`. The wizard labels `/volume1` as `data`, `/volume2` as `data2`, and so on.

The setup page listens on port 8765. Change the published port in the Compose file if it is already taken.

## Configure in the browser

1. Open `http://NAS-IP:8765` from a computer on the same trusted LAN.
2. In UGOS Docker, open the `setup` container's log and copy the setup token. The `reader` container has a separate log. The token proves that you control the NAS; keep it private.

   <p align="center">
     <img src="images/wizard-token-light.webp#gh-light-mode-only" width="100%" alt="The Unlock setup screen with an empty token field, light theme">
     <img src="images/wizard-token-dark.webp#gh-dark-mode-only" width="100%" alt="The Unlock setup screen with an empty token field, dark theme">
   </p>

3. Enter a display name and a **stable NAS ID**. Home Assistant identifies the device and its entities by this ID, so keep it unchanged later. Then enter the broker address, port, protocol and the dedicated MQTT login. The password is hidden by default and stays on the NAS.

   <p align="center">
     <img src="images/wizard-nas-light.webp#gh-light-mode-only" width="100%" alt="The NAS and MQTT screen with example values and a hidden password, light theme">
     <img src="images/wizard-nas-dark.webp#gh-dark-mode-only" width="100%" alt="The NAS and MQTT screen with example values and a hidden password, dark theme">
   </p>

4. Select the disks and volumes. The wizard lists SATA disks with their HDD/SSD type without reading SMART during discovery. Compare them with UGOS Storage before saving.

   <p align="center">
     <img src="images/wizard-storage-light.webp#gh-light-mode-only" width="100%" alt="The Disks and volumes screen with four HDDs and one volume selected, light theme">
     <img src="images/wizard-storage-dark.webp#gh-dark-mode-only" width="100%" alt="The Disks and volumes screen with four HDDs and one volume selected, dark theme">
   </p>

5. Choose the readings to publish and an interval for each group. SMART-based groups have a five-minute minimum, and volume-space checks are scheduled separately, so a short volume interval does not increase SMART polling.

   <p align="center">
     <img src="images/wizard-readings-light.webp#gh-light-mode-only" width="100%" alt="The Readings to publish screen with reading groups and their intervals, light theme">
     <img src="images/wizard-readings-dark.webp#gh-dark-mode-only" width="100%" alt="The Readings to publish screen with reading groups and their intervals, dark theme">
   </p>

6. Save. The publisher restarts with the new settings. New selections or samples can take up to about two minutes to reach MQTT.

## Check the result

In Home Assistant, open the MQTT integration and find the new NAS device. CPU and memory usage should update within a couple of minutes, and HDD and volume readings after the next sample. HDD diagnostic counters are disabled by default; enable the entities you want.

Do not paste the setup token, MQTT password, or full container logs into an issue. Redact disk serial numbers and private addresses from anything you share.

## Update

Read the release notes and the [changelog](../CHANGELOG.md) first: a version that changes the stored settings format must say so. Then update the project's image in UGOS Docker and redeploy it. With the source build, replace the files in the project folder and rebuild the project instead. Either way, the settings and MQTT password stay in the project's named volumes whose names end in `telemetry_config` and `telemetry_secrets`. The [release and update policy](release-and-updates.md) has the details.

## Remove

Stop and delete the project in UGOS Docker. To remove the saved settings and the MQTT password too, also delete its volumes whose names end in `telemetry_config` and `telemetry_secrets`. Retained MQTT Discovery messages stay on the broker until they are cleared, and the Home Assistant device keeps its history until you delete it there.
