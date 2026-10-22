import unittest
from unittest import mock

from gst_utils import MetadataValidator, _identify_gst_bin_from_snap


class TestIdentifyGstBinFromSnap(unittest.TestCase):
    def _which_result(self, returncode, stdout):
        result = mock.Mock()
        result.returncode = returncode
        result.stdout = stdout
        return result

    @mock.patch("gst_utils.subprocess.run")
    def test_snap_binary_detected(self, mock_run):
        mock_run.return_value = self._which_result(
            0, b"/snap/bin/gst-launch-1.0\n"
        )
        self.assertTrue(_identify_gst_bin_from_snap("gst-launch-1.0"))

    @mock.patch("gst_utils.subprocess.run")
    def test_deb_binary_not_snap(self, mock_run):
        mock_run.return_value = self._which_result(
            0, b"/usr/bin/gst-launch-1.0\n"
        )
        self.assertFalse(_identify_gst_bin_from_snap("gst-launch-1.0"))

    @mock.patch("gst_utils.subprocess.run")
    def test_missing_binary_exits(self, mock_run):
        mock_run.return_value = self._which_result(1, b"")
        with self.assertRaises(SystemExit):
            _identify_gst_bin_from_snap("gst-launch-1.0")


class TestMetadataValidatorCodec(unittest.TestCase):
    @mock.patch(
        "gst_utils.execute_command",
        return_value="Topology:\n  container #0: WebM\n    video #1: VP9\n",
    )
    def test_vp9_encoder_codec_is_mapped(self, _):
        validator = MetadataValidator(file_path="out.webm")
        # Raises SystemExit when the codec is unmapped or missing.
        validator.validate("codec", "v4l2vp9enc").is_valid()


if __name__ == "__main__":
    unittest.main()
