import unittest

from camera_utils import CameraResources


class TestCameraResourcesItems(unittest.TestCase):
    """Resource generation: composed name and camera_id override."""

    def _item(self, **overrides):
        item = {
            "camera": "imx219",
            "method": "gstreamer",
            "physical_interface": "cam0",
            "v4l2_device_name": "vi-output, imx219 9-0010",
            "formats": ["NV12"],
            "resolutions": [{"width": 1920, "height": 1080}],
        }
        item.update(overrides)
        return item

    def test_capture_image_default_identifier(self):
        resources = CameraResources()
        resources._current_scenario_name = "capture_image"
        resources.capture_image([self._item()])

        self.assertEqual(len(resources._resource_items), 1)
        record = resources._resource_items[0]
        self.assertEqual(
            record["name"], "imx219_cam0_gstreamer_1920x1080_NV12"
        )
        self.assertEqual(
            record["v4l2_device_name"], "vi-output, imx219 9-0010"
        )
        self.assertNotIn("mode", record)

    def test_record_video_camera_id_override_and_mode(self):
        resources = CameraResources()
        resources._current_scenario_name = "record_video"
        item = self._item(
            camera_id="0",
            resolutions=[
                {"width": 1920, "height": 1080, "fps": 30, "mode": 2}
            ],
        )
        del item["v4l2_device_name"]
        resources.record_video([item])

        self.assertEqual(len(resources._resource_items), 1)
        record = resources._resource_items[0]
        self.assertEqual(
            record["name"], "imx219_cam0_gstreamer_1920x1080@30fps_mode2_NV12"
        )
        # camera_id overrides the default identifier
        self.assertEqual(record["v4l2_device_name"], "0")
        self.assertEqual(record["mode"], 2)
        self.assertEqual(record["fps"], 30)

    def test_missing_identifier_skips_item(self):
        resources = CameraResources()
        resources._current_scenario_name = "capture_image"
        item = self._item()
        del item["v4l2_device_name"]
        resources.capture_image([item])

        self.assertEqual(resources._resource_items, [])


if __name__ == "__main__":
    unittest.main()
