import unittest
from unittest import mock

from camera_utils import CameraResources, execute_command


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

    def test_capture_image_optional_fps(self):
        resources = CameraResources()
        resources._current_scenario_name = "capture_image"
        item = self._item(
            camera_id="0",
            resolutions=[
                {"width": 3280, "height": 2464, "fps": 21, "mode": 0}
            ],
        )
        resources.capture_image([item])

        record = resources._resource_items[0]
        # capture fps pins slow sensor modes but stays out of the job name
        self.assertEqual(record["fps"], 21)
        self.assertEqual(
            record["name"], "imx219_cam0_gstreamer_3280x2464_mode0_NV12"
        )

    def test_missing_identifier_skips_item(self):
        resources = CameraResources()
        resources._current_scenario_name = "capture_image"
        item = self._item()
        del item["v4l2_device_name"]
        resources.capture_image([item])

        self.assertEqual(resources._resource_items, [])


class TestExecuteCommandGstEnv(unittest.TestCase):
    GST_BIN = "/usr/bin/gst-launch-1.0"

    @mock.patch("camera_utils.GST_LAUNCH_BIN", GST_BIN)
    @mock.patch("camera_utils.gst_utils.get_gst_env")
    @mock.patch("camera_utils.subprocess.run")
    def test_gst_pipeline_gets_gst_env(self, mock_run, mock_env):
        mock_env.return_value = {"GST_PLUGIN_PATH": "/usr/lib/gst"}
        mock_run.return_value.stdout = "done"
        cmd = "/usr/bin/env -u DISPLAY {} videotestsrc ! fakesink".format(
            self.GST_BIN
        )
        self.assertEqual(execute_command(cmd), "done")
        mock_env.assert_called_once_with(self.GST_BIN)
        self.assertEqual(
            mock_run.call_args.kwargs["env"],
            {"GST_PLUGIN_PATH": "/usr/lib/gst"},
        )

    @mock.patch("camera_utils.GST_LAUNCH_BIN", GST_BIN)
    @mock.patch("camera_utils.gst_utils.get_gst_env")
    @mock.patch("camera_utils.subprocess.run")
    def test_other_tools_inherit_env(self, mock_run, mock_env):
        execute_command("v4l2-ctl --list-devices")
        mock_env.assert_not_called()
        self.assertIsNone(mock_run.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
