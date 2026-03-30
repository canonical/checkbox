# RZ Test Scenario and Test Setup

This directory contains the scenario definitions and test setup configurations for the RZ platform (e.g. RZ/G2L `rzv2l` target) running the OV5645 MIPI CSI camera.

## Contents

- `rzg_v_mipi_camera_test_scenario_ov5645.json`: This file defines the various resolutions, formats, and actions (e.g. `capture_image`, `record_video`) that Checkbox will iterate through during camera testing on the RZ platform.
- `rzg_v_mipi_camera_test_setup_ov5645.json`: This configuration file is used by `media-ctl` to correctly map the sensor pipeline nodes to the proper media nodes before testing.

## Camera Configuration Details

### OV5645

The OV5645 camera is configured to support the following resolutions/frame rates:
- **Formats:** YUV
- **Connections:** Interfaced through MIPI CSI
- **Testing Methods:** GStreamer
- **Supported resolutions:** 1280x960, 1920x1080, 2592x1944

Please refer to https://renesas-wiki.atlassian.net/wiki/spaces/REN/pages/1016843/Camera for more details.
Also the data sheet about ov5645 is here: https://www.v-visiontech.com/web/userfiles/download/OV5645_CSP3_DS_1.1_KingHornInternationalLtd..pdf

These tests use the custom tooling paths provided by the `rz-camera-ov5645` snap via environment variables, ensuring compatibility between Checkbox and the underlying RZ platform drivers.
