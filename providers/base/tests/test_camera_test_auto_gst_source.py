import unittest as ut
from unittest.mock import MagicMock, patch
from shlex import split as sh_split
import sys


mock_gi = MagicMock()


@patch.dict(
    sys.modules,
    {
        "gi": mock_gi,
        "gi.repository": mock_gi.repository,
        "logging": MagicMock(),
    },
)
class CameraTestAutoGstSourceTests(ut.TestCase):
    def test_correct_subcommand_is_executed(self):
        import camera_test_auto_gst_source as CTAGS

        with patch("os.path.isdir") as mock_isdir, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "camera_test_auto_gst_source.get_devices"
        ) as mock_get_devices, patch(
            "camera_test_auto_gst_source.cam"
        ) as mock_cam, patch(
            "camera_test_auto_gst_source.MediaValidator"
        ) as mock_validator:
            mock_isdir.return_value = True
            mock_isfile.return_value = True
            mock_get_devices.return_value = [MagicMock()]
            mock_validator.validate_image_dimensions.return_value = True

            # print(dir(mock_cam.take_photo))
            mock_resolver = MagicMock()
            mock_cam.CapsResolver.return_value = mock_resolver
            mock_resolver.get_all_fixated_caps.return_value = [MagicMock()]

            with patch(
                "sys.argv",
                sh_split(
                    "camera_test_auto_gst_source.py take-photo -p some/dir"
                ),
            ):
                CTAGS.main()
                print(dir(mock_cam.take_photo))
                self.assertEqual(mock_cam.take_photo.call_count, 1)

            with patch(
                "sys.argv",
                sh_split(
                    "camera_test_auto_gst_source.py record-video "
                    "-p some/dir --encoding mp4_h264"
                ),
            ):
                CTAGS.main()
                self.assertEqual(mock_cam.record_video.call_count, 1)

            with patch(
                "sys.argv",
                sh_split("camera_test_auto_gst_source.py show-viewfinder"),
            ):
                CTAGS.main()
                self.assertEqual(mock_cam.show_viewfinder.call_count, 1)
    def test_correct_subcommand_is_executed(self):
        ...


if __name__ == "__main__":
    ut.main()
