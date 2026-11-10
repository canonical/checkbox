import argparse
import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "bin",
    "dragonwing_camera_test.py",
)

spec = importlib.util.spec_from_file_location(
    "dragonwing_camera_test", SCRIPT_PATH
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestDragonwingCameraTest(unittest.TestCase):
    def test_get_camera_list_rejects_missing_or_invalid_ids(self):
        for entry in (
            "OV5640",
            "OV5640:",
            ":2",
            "OV5640:two",
            "OV5640:-1",
            "OV5640:1:2",
            "1:2",
        ):
            for raise_error in (True, False):
                with self.subTest(entry=entry, raise_error=raise_error):
                    args = argparse.Namespace(
                        cameras="imx688:2 " + entry,
                        raise_error=raise_error,
                    )
                    with patch.object(
                        module,
                        "read_json_file",
                        return_value={"imx688": ["1080p"]},
                    ), patch.object(
                        module,
                        "find_csi_interface_for_sensor",
                        return_value={},
                    ), patch.object(
                        module.logging, "error"
                    ) as mock_error:
                        out = io.StringIO()
                        with redirect_stdout(out):
                            result = module.get_camera_list(args)
                    self.assertEqual(result, 1)
                    self.assertEqual(out.getvalue(), "")
                    mock_error.assert_called_once()

    def test_name_only_entry_recommends_mapping_helper(self):
        with self.assertRaisesRegex(
            ValueError, "dragonwing-camera-map-helper.py"
        ):
            module.parse_camera_entry("imx688")

    def test_get_camera_list_reports_csi_interface(self):
        args = argparse.Namespace(cameras="2:OV5640", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"OV5640": ["1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 1, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("camera: 2", out.getvalue())
        self.assertIn("csi: 1", out.getvalue())

    def test_get_camera_list_accepts_name_and_id_mapping(self):
        args = argparse.Namespace(cameras="OV5640:2", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"OV5640": ["1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 3, "slot": 2, "cci": 1},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("name: OV5640", out.getvalue())
        self.assertIn("camera: 2", out.getvalue())
        self.assertIn("csi: 3", out.getvalue())

    def test_get_camera_list_accepts_cmk_prefixed_sensor_name(self):
        args = argparse.Namespace(cameras="cmk_imx577:0", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx577": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 2, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("name: imx577", out.getvalue())
        self.assertIn("camera: 0", out.getvalue())
        self.assertIn("csi: 2", out.getvalue())

    def test_get_camera_list_skips_unavailable_cameras(self):
        args = argparse.Namespace(cameras="imx688:2 imx57:3", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx688": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 4, "slot": 1, "cci": 0},
        ), patch.object(
            module.logging, "error"
        ) as mock_error:
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 1)
        rendered = out.getvalue()
        self.assertIn("name: imx688", rendered)
        mock_error.assert_called_once_with(
            "Unavailable cameras: %s",
            "imx57",
        )

    def test_get_camera_list_silently_skips_unavailable_in_quiet_mode(self):
        args = argparse.Namespace(
            cameras="imx688:2 imx57:3", raise_error=False
        )

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx688": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 4, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        rendered = out.getvalue()
        self.assertIn("name: imx688", rendered)
        self.assertNotIn("Skipping unavailable camera", rendered)
        self.assertNotIn("Cannot find resolutions for imx57", rendered)
        self.assertNotIn("ERROR", rendered)
