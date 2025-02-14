# This is a file introducing Vendor Specific Camera test jobs

## id: mipi_camera_resource
  This resource job requires the Checkbox environment variable `MIPI_SCENARIO_DEFINITION_FILE_PATH`.
  - `MIPI_SCENARIO_DEFINITION_FILE_PATH`: The path of JSON file defines a bunch of scenarios that target cameras should perform.

## id: mipi-camera/capture-image_{{ camera }}_{{ physical_interface }}_{{ method }}_{{ width }}x{{ height }}_{{ format }}
## id: mipi-camera/record-video_{{ camera }}_{{ physical_interface }}_{{ method }}_{{ width }}x{{ height }}@{{ fps }}fps_{{ format }}
  Above two template jobs are generated based on the output of mipi_camera_resource.
  Additionally, you might need two Checkbox environment variables `PLATFORM_NAME`
  and `MIPI_CAMERA_SETUP_CONF_FILE_PATH` before testing.

  - `PLATFORM_NAME`: The platform name of DUT
  - `MIPI_CAMERA_SETUP_CONF_FILE_PATH`: The path of setup conf in JSON format if your camera need to configure the fmt and resolution of pads or set links of pads.

## Real Example

### Genio 350

- Cameras: Dual Onsemi Ap1302 + AR0430
- Content of Scenario JSON file (`MIPI_SCENARIO_DEFINITION_FILE_PATH`)
```json
{
    "capture_image": [
        {
            "camera": "onsemi_ap1302_ar0430",
            "method": "gstreamer",
            "physical_interface": "csi0",
            "v4l2_deivce_name": "mtk-camsv-isp30 (platform:15050000.camsv)",
            "formats": ["UYVY"],
            "resolutions": [
                {"width": 400, "height": 300},
                {"width": 720, "height": 480},
                {"width": 1280, "height": 720},
                {"width": 1920, "height": 1080}
            ]
        },
        {
            "camera": "onsemi_ap1302_ar0430",
            "method": "gstreamer",
            "physical_interface": "csi1",
            "v4l2_deivce_name": "mtk-camsv-isp30 (platform:15050800.camsv)",
            "formats": ["UYVY"],
            "resolutions": [
                {"width": 400, "height": 300},
                {"width": 720, "height": 480},
                {"width": 1280, "height": 720},
                {"width": 1920, "height": 1080}
            ]
        }
    ],
    "record_video": [
        {
            "camera": "onsemi_ap1302_ar0430",
            "method": "gstreamer",
            "physical_interface": "csi0",
            "v4l2_deivce_name": "mtk-camsv-isp30 (platform:15050000.camsv)",
            "formats": ["UYVY"],
            "resolutions": [
                {"width": 400, "height": 300, "fps": 30},
                {"width": 720, "height": 480, "fps": 30},
                {"width": 1280, "height": 720, "fps": 30},
                {"width": 1920, "height": 1080, "fps": 30}
            ]
        },
        {
            "camera": "onsemi_ap1302_ar0430",
            "method": "gstreamer",
            "physical_interface": "csi1",
            "v4l2_deivce_name": "mtk-camsv-isp30 (platform:15050800.camsv)",
            "formats": ["UYVY"],
            "resolutions": [
                {"width": 400, "height": 300, "fps": 30},
                {"width": 720, "height": 480, "fps": 30},
                {"width": 1280, "height": 720, "fps": 30},
                {"width": 1920, "height": 1080, "fps": 30}
            ]
        }
    ]
}
```
- Content of Setup JSON file (`MIPI_CAMERA_SETUP_CONF_FILE_PATH`)
```json
{
    "media_node_v4l2_name": "mtk-camsys-3.0 (platform:15040000.seninf)",
    "cameras": [
        {
            "physical_interface": "csi0",
            "pads": [
                {
                    "action": "set_format",
                    "node": "ap1302.2-003d",
                    "source": 2,
                    "fmt": "UYVY8_1X16"
                },
                {
                    "action": "set_format",
                    "node": "15040000.seninf",
                    "source": 4,
                    "fmt": "UYVY8_1X16"
                },
                {
                    "action": "set_format",
                    "node": "15050000.camsv",
                    "source": 1,
                    "fmt": "UYVY8_1X16"
                }
            ],
            "links": []
        },
        {
            "physical_interface": "csi1",
            "pads": [
                {
                    "action": "set_format",
                    "node": "ap1302.3-003d",
                    "source": 2,
                    "fmt": "UYVY8_1X16"
                },
                {
                    "action": "set_format",
                    "node": "15040000.seninf",
                    "source": 5,
                    "fmt": "UYVY8_1X16"
                },
                {
                    "action": "set_format",
                    "node": "15050800.camsv",
                    "source": 1,
                    "fmt": "UYVY8_1X16"
                }
            ],
            "links": []
        }
    ]
}
```
