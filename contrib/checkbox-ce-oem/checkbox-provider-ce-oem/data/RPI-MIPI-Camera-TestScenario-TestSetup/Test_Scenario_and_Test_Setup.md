# Test Scenario and Test Setup

This document provides test scenarios for the Raspberry Pi MIPI camera
configurations.

> **Note:** Raspberry Pi cameras are driven through the libcamera stack via
> rpicam-apps. No media-ctl test setup files are required — only test scenario
> files.

> **Note:** All captures use the camera's native Bayer format selected via the
> `--mode` flag (`WxHxBIT`). No encoder is used for still images; video is
> recorded in H.264 by rpicam-vid.

> **Note:** every item declares `camera_id` — the libcamera enumeration index
> (0 / 1) — instead of the framework's default `v4l2_device_name` identifier.
> libcamera addresses sensors by the order they are detected; on the CM5 IO
> board a sensor on CAM/DISP0 is typically index 0 and a sensor on CAM/DISP1
> is typically index 1. Run `rpicam-still --list-cameras` on the DUT to
> confirm the index before populating the scenario file.

## Required Checkbox Environment

The capture tools (`rpicam-still` and `rpicam-vid`) must be reachable from
the checkbox jobs. Making them so is a pre-test setup step.

**Classic / deb images** — install the `rpicam-apps` package:

```bash
sudo apt install rpicam-apps
```

The tools land in `/usr/bin/` which is on `PATH`, so no additional
configuration is needed.

## Overview

The test scenario files are located in the
`contrib/checkbox-ce-oem/checkbox-provider-ce-oem/data/RPI-MIPI-Camera-TestScenraio-TestSetup`
directory.

## Raspberry Pi Camera Configurations

Raspberry Pi configurations only require test scenario files (no test setup
needed).

### IMX219 (Camera Module 2)

**Test Scenario:**

- Hardware: Raspberry Pi Camera Module 2 (Sony IMX219, 8 MP)
- Board: Raspberry Pi CM5 IO board
- Documentation:
  - [Camera Module 2 product page](https://www.raspberrypi.com/products/camera-module-v2/)
  - [Camera Module 2 documentation](https://www.raspberrypi.com/documentation/accessories/camera.html#camera-module-2)
  - [Hardware specifications](https://www.raspberrypi.com/documentation/accessories/camera.html#hardware-specification)
  - [Arducam IMX219 (RPI native) documentation](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/8MP-IMX219/)
- Configuration (one file per carrier-board connector):
  - [`rpi_mipi_camera_test_scenario_imx219_cam0.json`](rpi_mipi_camera_test_scenario_imx219_cam0.json)

> **Note:** the single module can be fitted on either CM5 IO board connector
> (`CAM/DISP0` / `CAM/DISP1`). The connector label is part of every job id,
> so there is one scenario file per connector. Point
> `MIPI_SCENARIO_DEFINITION_FILE_PATH` at the file matching the DUT's
> wiring. `camera_id` is `0` when only one camera is connected — libcamera
> enumerates the detected sensors starting from 0, regardless of which
> physical connector is used.

**Still image capture (rpicam-still):**

| Resolution | Formats |
| --- | --- |
| 3280×2464 | SRGGB10_CSI2P, SRGGB8 |
| 1920×1080 | SRGGB10_CSI2P, SRGGB8 |
| 1640×1232 | SRGGB10_CSI2P, SRGGB8 |
| 640×480   | SRGGB10_CSI2P, SRGGB8 |

**Video recording (rpicam-vid):**

| Resolution | FPS |
| --- | --- |
| 640×480   | 206 |
| 1640×1232 | 41  |
| 1920×1080 | 47  |

> **Note:** the FPS values above are the IMX219 native maximum frame rates at
> each resolution as published in the Raspberry Pi hardware specification
> (`1080p47`, `1640×1232p41`, `640×480p206`). The 3280×2464 full-resolution
> mode is excluded from video recording as it runs at only ~21 fps and is not
> listed in the official video modes.

> **Note:** format selection in the `--mode` flag uses the pixel format string
> (`SRGGB10_CSI2P` → 10-bit packed Bayer RGGB, `SRGGB8` → 8-bit Bayer RGGB).
> The rpicam format mapping is: `SRGGB10_CSI2P` → `10`, `SRGGB8` → `8`, which
> is appended to the mode string as `WxHxBIT` (e.g. `--mode 640:480:10`).

## Capture Methods

- `rpicam-still` — libcamera still-image capture tool, saves as JPEG (`.jpg`)
- `rpicam-vid` — libcamera video recording tool, saves as H.264 (`.h264`)

## Hardware Setup

Connect the Camera Module 2 to the CM5 IO board:

1. Shut down the CM5 and disconnect it from power.
2. Locate the camera connector on the CM5 IO board. The two connectors are
   at the left end of the furthest edge, labelled `CAM/DISP0` and
   `CAM/DISP1`. Either connector can be used.
3. Lift the flap of the chosen connector, insert the camera cable with the
   metallic contacts facing away from the flap, then press the flap down
   until it clicks.
4. Connect the other end of the cable to the camera module in the same way.
5. Power on the CM5 and verify detection:

```bash
rpicam-still --list-cameras
```

Expected output (index `0` for a single camera):

```
Available cameras
-----------------
0 : imx219 [3280x2464 10-bit RGGB] (...)
    Modes: 'SRGGB10_CSI2P' : 640x480 1640x1232 1920x1080 3280x2464
           'SRGGB8'         : 640x480 1640x1232 1920x1080 3280x2464
```

The `0` shown is the `camera_id` value to use in the scenario JSON.

## Quick Reference

| Configuration | Board | Test Scenario | Test Setup | Cameras |
| --- | --- | --- | --- | --- |
| IMX219 (cam0) | Raspberry Pi CM5 IO board | ✅ Required | ❌ Not needed | 1 |
