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

The capture tools (`gst-launch-1.0` with the NVIDIA plugins, and
`nvargus_nvraw`) must be reachable from the checkbox jobs — making them so
is a pre-test setup step, not the test's job. `nvargus_nvraw` is resolved
from `PATH`; the jobs pass `GST_LAUNCH_BIN`, `GST_PLUGIN_PATH`,
`GST_PLUGIN_SYSTEM_PATH` and `GST_PLUGIN_SCANNER` through from the checkbox
configuration, so each image type supplies what it needs:

**Classic / deb images** — the NVIDIA GStreamer plugins are off the default
search path:

```ini
GST_LAUNCH_BIN=/usr/bin/gst-launch-1.0
GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0/
```

**Ubuntu Core images** — checkbox-ce-oem carries no NVIDIA stack. Install
the NVIDIA multimedia snap (which hosts the Argus daemon and its own
GStreamer with the NVIDIA plugins) and alias its tools to the classic
command names before testing:

```bash
sudo snap alias <multimedia-snap>.gst-launch gst-launch-1.0
sudo snap alias <multimedia-snap>.nvargus-nvraw nvargus_nvraw
```

The multimedia snap resolves its own plugin paths, so no `GST_PLUGIN_*`
variables are needed. The aliases land in `/snap/bin`, which is on `PATH`,
so `nvargus_nvraw` resolves without configuration; if the job environment
misses it for gst, point the override at the alias:

```ini
GST_LAUNCH_BIN=/snap/bin/gst-launch-1.0
```

> **Note:** snap-packaged checkbox pre-exports `GST_PLUGIN_SYSTEM_PATH` and
> `GST_PLUGIN_SCANNER` in its wrapper, and checkbox only injects config
> `[environment]` values for variables that are not already set — so
> `GST_PLUGIN_*` overrides take no effect under a checkbox snap (verified on
> checkbox 7.3.0). This is one more reason the multimedia-snap aliases are
> the supported route on Ubuntu Core: the aliased tools run inside the
> multimedia snap where its own plugin paths and Argus socket apply, and
> `GST_LAUNCH_BIN` (not preset, always injects) can point at the alias.

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

> **Note:** the single module can be fitted on either carrier-board
> connector (`cam0` / `cam1`), and the connector label is part of every job
> id, so there is one scenario file per connector. Point
> `MIPI_SCENARIO_DEFINITION_FILE_PATH` at the file matching the DUT's
> wiring — the current certification Orin NX and Orin Nano DUTs both carry
> the module on `cam0`. `camera_id` stays `0` in both files: Argus indexes
> the sensors it detects, not the connectors.

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
