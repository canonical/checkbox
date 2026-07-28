import unittest
from unittest.mock import patch
import tempfile
import os

from bin.platform_config_resource import (
    detect_vaapi_encoders,
    detect_vaapi_decoders,
    read_config_file,
    emit_resources,
    ENCODER_MAP,
    detect_gpu_vendor,
)


class TestDetectVaapiEncoders(unittest.TestCase):
    @patch("bin.platform_config_resource.run_vainfo")
    def test_detect_encoders_found(self, mock_vainfo):
        mock_vainfo.return_value = "VAProfileH264...\nVAProfileVP9..."
        result = detect_vaapi_encoders()
        self.assertIn("h264", result)
        self.assertTrue(result["h264"])
        self.assertIn("vp9", result)
        self.assertTrue(result["vp9"])

    @patch("bin.platform_config_resource.run_vainfo")
    def test_detect_encoders_not_found(self, mock_vainfo):
        mock_vainfo.return_value = "No VA-API support"
        result = detect_vaapi_encoders()
        for codec in ENCODER_MAP:
            self.assertNotIn(codec, result)

    @patch("bin.platform_config_resource.run_vainfo")
    def test_detect_encoders_vainfo_empty(self, mock_vainfo):
        mock_vainfo.return_value = ""
        result = detect_vaapi_encoders()
        self.assertEqual(result, {})


class TestDetectVaapiDecoders(unittest.TestCase):
    @patch("bin.platform_config_resource.run_vainfo")
    def test_detect_decoders_found(self, mock_vainfo):
        mock_vainfo.return_value = "VAProfileH264High\nVAProfileVP9Profile0"
        result = detect_vaapi_decoders()
        self.assertIn("h264-high", result)
        self.assertIn("vp9-profile0", result)

    @patch("bin.platform_config_resource.run_vainfo")
    def test_detect_decoders_not_found(self, mock_vainfo):
        mock_vainfo.return_value = ""
        result = detect_vaapi_decoders()
        self.assertEqual(result, {})


class TestReadConfigFile(unittest.TestCase):
    def test_read_config_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as f:
            f.write("[platform]\n")
            f.write("arch = x86_64\n")
            f.write("gpu_vendor = intel\n")
            f.write("[encoder]\n")
            f.write("h264 = True\n")
            f.write("h265 = False\n")
            f.write("[decoder]\n")
            f.write("av1-profile0 = True\n")
            path = f.name
        try:
            result = read_config_file(path)
            self.assertEqual(result["arch"], "x86_64")
            self.assertEqual(result["gpu_vendor"], "intel")
            self.assertEqual(result["encoder_h264"], "True")
            self.assertEqual(result["encoder_h265"], "False")
            self.assertEqual(result["decoder_av1-profile0"], "True")
        finally:
            os.unlink(path)

    def test_read_config_file_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as f:
            f.write("")
            path = f.name
        try:
            result = read_config_file(path)
            self.assertEqual(result, {})
        finally:
            os.unlink(path)


class TestEmitResources(unittest.TestCase):
    def test_emit_resources(self):
        resources = {"arch": "x86_64", "encoder_h264": "True"}
        with patch("builtins.print") as mock_print:
            emit_resources(resources)
            mock_print.assert_any_call("arch: x86_64")
            mock_print.assert_any_call("encoder_h264: True")

    def test_emit_resources_sorted(self):
        resources = {"b": "2", "a": "1"}
        with patch("builtins.print") as mock_print:
            emit_resources(resources)
            calls = [call[0][0] for call in mock_print.call_args_list]
            self.assertEqual(calls, ["a: 1", "b: 2"])


class TestDetectGpuVendor(unittest.TestCase):
    def test_detect_intel(self):
        output = "vainfo: VA-API version: 1.20 (libva 2.22.0)\n"
        output += "intel\n"
        self.assertEqual(detect_gpu_vendor(output), "intel")

    def test_detect_unknown(self):
        output = "vainfo: no adapters found"
        self.assertEqual(detect_gpu_vendor(output), "unknown")


class TestMain(unittest.TestCase):
    @patch("bin.platform_config_resource.platform.machine")
    @patch("bin.platform_config_resource.run_vainfo")
    @patch("bin.platform_config_resource.emit_resources")
    def test_main_auto_detect(self, mock_emit, mock_vainfo, mock_machine):
        mock_machine.return_value = "x86_64"
        mock_vainfo.return_value = "VAProfileH264...\nVAProfileVP9..."

        from bin.platform_config_resource import main

        main()
        mock_emit.assert_called_once()
        resources = mock_emit.call_args[0][0]
        self.assertEqual(resources["arch"], "x86_64")
        self.assertEqual(resources["encoder_h264"], "True")

    @patch("bin.platform_config_resource.os.environ")
    @patch("bin.platform_config_resource.read_config_file")
    @patch("bin.platform_config_resource.emit_resources")
    @patch("bin.platform_config_resource.os.path.exists")
    def test_main_with_config(
        self, mock_exists, mock_emit, mock_read, mock_environ
    ):
        mock_environ.get.return_value = "/path/to/config.ini"
        mock_exists.return_value = True
        mock_read.return_value = {
            "arch": "aarch64",
            "encoder_h264": "True",
        }
        from bin.platform_config_resource import main

        main()
        mock_read.assert_called_once_with("/path/to/config.ini")
        resources = mock_emit.call_args[0][0]
        self.assertEqual(resources["arch"], "aarch64")


if __name__ == "__main__":
    unittest.main()
