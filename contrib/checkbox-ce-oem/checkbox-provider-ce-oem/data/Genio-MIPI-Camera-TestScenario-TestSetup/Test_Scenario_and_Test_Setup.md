# Test Scenario and Test Setup

This document provides test scenarios and test setup configurations for different camera configurations on Genio MIPI Camera systems.

> **Note:** Not all the test scenarios and test setup files are available in here, you can based on [Genio MIPI Camera Guide](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-common.html) to create the test scenario and test setup files.

## Overview

The test scenarios and test setup files are located in the `contrib/checkbox-ce-oem/checkbox-provider-ce-oem/data/Genio-MIPI-Camera-TestScenario-TestSetup` directory.

## V4L2 Sensor Configurations

V4L2 Sensor configurations require both test scenario and test setup files to be configured.

### ONSEMI_AP1302_AR0830

**Test Scenario:**

- Documentation: [G1200 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-v4l2-yuv.html)
- Documentation: [G700 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g700-evk-v4l2-yuv.html)
- Configuration: [`genio_mipi_camera_test_scenario_AP1302_AR0830.json`](genio_mipi_camera_test_scenario_AP1302_AR0830.json)

**Test Setup:**

- Documentation: [G1200 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-v4l2-yuv.html)
- Documentation: [G700 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g700-evk-v4l2-yuv.html)
- Configuration: [`genio_mipi_camera_test_setup_AP1302_AR0830.json`](genio_mipi_camera_test_setup_AP1302_AR0830.json)

**Formats and Resolutions:**

- [G1200 EVK Imgsensor YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-yuv.html)
- [G700 EVK Imgsensor YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g700-evk-imgsensor-yuv.html)

### ONSEMI_AP1302_AR0430 Dual

**Test Scenario:**

- Documentation: [G350 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g350-evk-v4l2-yuv.html)
- Configuration: [`genio_mipi_camera_test_scenario_AP1302_AR0430_dual.json`](genio_mipi_camera_test_scenario_AP1302_AR0430_dual.json)

**Test Setup:**

- Documentation: [G350 EVK V4L2 YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g350-evk-v4l2-yuv.html)
- Configuration: [`genio_mipi_camera_test_setup_AP1302_AR0430_dual.json`](genio_mipi_camera_test_setup_AP1302_AR0430_dual.json)

### ONSEMI_AR0430 Dual

**Test Scenario:**

- Documentation: [G350 EVK V4L2 RAW](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g350-evk-v4l2-raw.html)
- Configuration: [`genio_mipi_camera_test_scenario_AR0430_dual.json`](genio_mipi_camera_test_scenario_AR0430_dual.json)

> **Note:** The ONSEMI_AR0430 sensor only supports v4l2-ctl capture method (gstreamer pipeline not supported), and the picture/video is in RAW (bayer) frames in SGRBG10 packed format.

**Test Setup:**

- Documentation: [G350 EVK V4L2 RAW](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g350-evk-v4l2-raw.html)
- Configuration: [`genio_mipi_camera_test_setup_AR0430_dual.json`](genio_mipi_camera_test_setup_AR0430_dual.json)

## Mediatek Imgsensor Configurations

Mediatek Imgsensor configurations only require test scenario files (no test setup needed).

### IMX214 Dual and ONSEMI_AP1302_AR0830

**Test Scenario:**

- Documentation: [G1200 EVK Imgsensor RAW](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-raw.html)
- Documentation: [G1200 EVK Imgsensor YUV](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-yuv.html)
- Documentation: [G1200 EVK Imgsensor Multi](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-multi.html)
- Configuration: [`genio_mipi_camera_test_scenario_IMX214_AP1302_AR0830_IMX214.json`](genio_mipi_camera_test_scenario_IMX214_AP1302_AR0830_IMX214.json)

> **Note:** Only the G1200 EVK supports up to 3 cameras.

### IMX214 Dual

**Test Scenario:**

- Documentation: [G1200 EVK Imgsensor RAW](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-raw.html)
- Documentation: [G700 EVK Imgsensor RAW](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g700-evk-imgsensor-raw.html)
- Documentation: [G1200 EVK Imgsensor Multi](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g1200-evk-imgsensor-multi.html)
- Documentation: [G700 EVK Imgsensor Multi](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/app-dev/camera/camera-g700-evk-imgsensor-multi.html)
- Configuration: [`genio_mipi_camera_test_scenario_IMX214_dual.json`](genio_mipi_camera_test_scenario_IMX214_dual.json)

## Quick Reference

| Configuration | Type | Test Scenario | Test Setup | Max Cameras |
|---------------|------|---------------|------------|-------------|
| ONSEMI_AP1302_AR0830 | V4L2 | ✅ Required | ✅ Required | 1 |
| ONSEMI_AP1302_AR0430 Dual | V4L2 | ✅ Required | ✅ Required | 2 |
| ONSEMI_AR0430 Dual | V4L2 | ✅ Required | ✅ Required | 2 |
| IMX214 Dual + AP1302_AR0830 | Imgsensor | ✅ Required | ❌ Not needed | 3 |
| IMX214 Dual | Imgsensor | ✅ Required | ❌ Not needed | 2 |
