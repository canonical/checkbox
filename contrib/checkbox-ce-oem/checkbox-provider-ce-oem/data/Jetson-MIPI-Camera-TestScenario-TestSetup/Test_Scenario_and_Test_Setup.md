# Test Scenario and Test Setup

This document provides test scenarios for the NVIDIA Jetson MIPI camera
configurations.

> **Note:** Jetson cameras are driven through the Argus stack. Argus owns the
> media graph, so no test setup (media-ctl) files are required — only test
> scenario files.

> **Note:** All captures use the camera's native format — NV12 for the Argus
> gstreamer path, Bayer raw for nvargus_nvraw. No encoder is used, so no test
> depends on NVENC.

> **Note:** every item declares an explicit Argus `mode` index per resolution.
> nvargus_nvraw passes it as `--mode`; gstreamer passes it as
> `nvarguscamerasrc sensor-mode=`. This is what makes sensor modes that share a
> resolution and frame rate (IMX274 modes 1 and 3) separately testable.

> **Note:** every item declares `camera_id` — the Argus `source_index`
> (0 / 1) — instead of the framework's default `v4l2_device_name` identifier.
> Argus addresses sensors by index; the Tegra v4l2 names embed an i2c bus
> number and a device-tree VI channel, neither of which tracks the sensor
> index (the AGX Orin's two sensors are on VI channels 0 and 2).

## Required Checkbox Environment

The NVIDIA GStreamer plugins (`nvarguscamerasrc`, `nvvidconv`) are not on
GStreamer's default search path, so the checkbox configuration must point
GStreamer at them (the jobs pass these variables through to the test):

```ini
# Deb / classic image
GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0/

# Snap (checkbox-ce-oem): the working pair covers both the checkbox
# runtime's core elements and the NVIDIA plugin dir
GST_PLUGIN_SYSTEM_PATH=/snap/checkbox-ce-oem/current/checkbox-runtime/usr/lib/aarch64-linux-gnu/gstreamer-1.0:/snap/checkbox-ce-oem/current/usr/lib/aarch64-linux-gnu/gstreamer-1.0
GST_PLUGIN_SCANNER=/snap/checkbox-ce-oem/current/checkbox-runtime/usr/lib/aarch64-linux-gnu/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner
```

`DISPLAY` is unset by the test itself (Argus tries to bring up an EGL
preview when it is set, which wedges headless runs), so nothing is needed
in the configuration for it.

## Overview

The test scenario files are located in the
`contrib/checkbox-ce-oem/checkbox-provider-ce-oem/data/Jetson-MIPI-Camera-TestScenario-TestSetup`
directory.

## Argus Sensor Configurations

Jetson configurations only require test scenario files (no test setup needed).

### IMX274 Dual

**Test Scenario:**

- Hardware: Leopard Imaging LI-JETSON-IMX274-DUAL-090H, 2x Sony IMX274
- Board: Jetson AGX Orin Developer Kit
- Documentation: [LI-JETSON-IMX274-DUAL-090H product page](https://leopardimaging.com/product/robotics-cameras/cis-2-mipi-modules/li-jetson-imx274-dual/)
- Documentation: [LI-JETSON-IMX274-DUAL-090H datasheet](https://leopardimaging.com/wp-content/uploads/2026/01/LI-JETSON-IMX274-DUAL-090H_Datasheet.pdf)
- Configuration: [`jetson_mipi_camera_test_scenario_imx274_dual.json`](jetson_mipi_camera_test_scenario_imx274_dual.json)

| Argus mode | Resolution | FPS |
| --- | --- | --- |
| 0 | 3840x2160 | 60 |
| 1 | 1920x1080 | 60 |
| 2 | 3840x2160 | 30 |
| 3 | 1920x1080 | 60 |

> **Note:** there is no 720p mode on this sensor. Modes 1 and 3 share
> resolution+fps (1920x1080@60) and differ only in gain/exposure range, so every
> job pins its mode explicitly (`--mode` / `sensor-mode=`) and the job id carries
> a `_modeN` suffix. All four modes are tested on all three capture paths (both
> sensors), for 24 jobs total.

> **Note:** the Leopard Imaging datasheet's "Supported Platform" line lists only
> the Nvidia Holoscan Platform and omits Jetson AGX Orin. The vendor product
> page's compatibility table does confirm AGX Orin support (Orin NX / Orin Nano /
> Nano are marked N/A there, consistent with those boards carrying the IMX219
> instead).

### IMX219

**Test Scenario:**

- Hardware: Arducam Nvidia Jetson native camera IMX219
- Boards: Jetson Orin NX, Jetson Orin Nano (same sensor, same mode set)
- Documentation: [Arducam Nvidia Jetson native camera IMX219](https://docs.arducam.com/Nvidia-Jetson-Camera/Native-Camera/imx219/) (L4T 35.x table)
- Configuration (one file per carrier-board connector):
  - [`jetson_mipi_camera_test_scenario_imx219_cam0.json`](jetson_mipi_camera_test_scenario_imx219_cam0.json)
  - [`jetson_mipi_camera_test_scenario_imx219_cam1.json`](jetson_mipi_camera_test_scenario_imx219_cam1.json)

> **Note:** the Orin NX and Orin Nano DUTs carry the same single module but
> fitted on different carrier-board connectors — one on `cam0`, the other on
> `cam1` — and the connector label is part of every job id. Point
> `MIPI_SCENARIO_DEFINITION_FILE_PATH` at the file matching where the module
> is fitted. `camera_id` stays `0` in both files: Argus indexes the sensors
> it detects, not the connectors.

| Argus mode | Resolution | FPS |
| --- | --- | --- |
| 0 | 3280x2464 | 21 |
| 1 | 3280x1848 | 28 |
| 2 | 1920x1080 | 30 |
| 3 | 1640x1232 | 30 |
| 4 | 1280x720 | 60 |

> **Note:** this is the Arducam L4T 35.x mode table, byte-identical on both
> boards. The Jetson Orin Nano has no NVENC hardware encoder, but because every
> capture here uses the sensor's native format with no encoder, NVENC is never
> needed — the Orin Nano supports video recording on all five modes like any
> other board.

## Capture Methods

- `gstreamer` — `nvarguscamerasrc sensor-mode=M` → NVMM NV12 → `nvvidconv` →
  `filesink` (raw, native NV12, no encoder)
- `nvargus_nvraw` — Argus CLI tool, native Bayer raw (`.nvraw`), explicit
  `--mode M`

## Quick Reference

| Configuration | Board(s) | Test Scenario | Test Setup | Cameras |
| --- | --- | --- | --- | --- |
| IMX274 Dual | Jetson AGX Orin Developer Kit | ✅ Required | ❌ Not needed | 2 |
| IMX219 | Jetson Orin NX, Jetson Orin Nano | ✅ Required | ❌ Not needed | 1 |
