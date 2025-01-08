import unittest as ut
from unittest.mock import MagicMock, patch
from shlex import split as sh_split
import sys
from io import StringIO
from pathlib import Path


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
    @patch("sys.stdout", new=StringIO())
    def test_correct_subcommand_is_executed(self):

        with patch("os.path.isdir") as mock_isdir, patch(
            "os.path.isfile"
        ) as mock_isfile, patch(
            "camera_test_auto_gst_source.get_devices"
        ) as mock_get_devices, patch(
            "camera_test_auto_gst_source.cam"
        ) as mock_cam, patch(
            "camera_test_auto_gst_source.MediaValidator"
        ) as mock_validator:
            import camera_test_auto_gst_source as CTAGS

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

    @patch("os.path.isfile")
    @patch("camera_test_auto_gst_source.logger")
    # @patch("camera_test_auto_gst_source.PIL.Image")
    @patch("camera_test_auto_gst_source.GstPbutils")
    def test_image_validator(
        self,
        mock_pbutils: MagicMock,
        mock_logger: MagicMock,
        mock_isfile: MagicMock,
    ):
        import camera_test_auto_gst_source as CTAGS

        expected_width = 640
        expected_height = 480

        mock_isfile.return_value = True
        self._make_mock_video_info(
            mock_pbutils, expected_width, expected_height
        )

        validator = CTAGS.MediaValidator()

        self.assertTrue(
            validator.validate_image_dimensions(
                Path("some/path"),
                expected_height=expected_height,
                expected_width=expected_width,
            )
        )

        bad_width = 1237219831
        self._make_mock_video_info(mock_pbutils, bad_width, expected_height)

        self.assertFalse(
            validator.validate_image_dimensions(
                Path("some/path"),
                expected_height=expected_height,
                expected_width=expected_width,
            )
        )

        mock_logger.error.assert_called_with(
            "Image width mismatch. Expected = {}, actual = {}".format(
                expected_width, bad_width
            )
        )

    @patch("camera_test_auto_gst_source.Gst")
    @patch("os.path.isfile")
    @patch("camera_test_auto_gst_source.GstPbutils")
    @patch("camera_test_auto_gst_source.logger")
    def test_video_validator(
        self,
        mock_logger: MagicMock,
        mock_pbutils: MagicMock,
        mock_isfile: MagicMock,
        mock_gst: MagicMock,
    ):
        import camera_test_auto_gst_source as CTAGS

        mock_gst.SECOND = 1

        expected_width = 640
        expected_height = 480
        expected_fps = 30
        expected_duration = 5

        self._make_mock_video_info(
            mock_pbutils,
            expected_width,
            expected_height,
            expected_fps,
            expected_duration,
        )
        mock_isfile.return_value = True
        validator = CTAGS.MediaValidator()
        result = validator.validate_video_info(
            Path("some/path"),
            expected_width=expected_width,
            expected_height=expected_height,
            expected_fps=expected_fps,
            expected_duration_seconds=expected_duration,
            duration_tolerance_seconds=0.5,
        )
        self.assertTrue(result)

    def _make_mock_video_info(
        self,
        mock_pbutils: MagicMock,
        width,
        height,
        fps=None,
        duration=None,
    ):
        # mock_discoverer = MagicMock()
        mock_pbutils.reset_mock()
        video_info = MagicMock()
        mock_pbutils.name = "mymockpbutils"
        if duration:
            video_info.get_duration.return_value = duration
        mock_pbutils.Discoverer.return_value = MagicMock()

        mock_pbutils.Discoverer().discover_uri.return_value = video_info
        video_stream = MagicMock()
        video_stream.get_width.return_value = width
        video_stream.get_height.return_value = height

        if fps:
            video_stream.get_framerate_num.return_value = fps

        video_info.get_video_streams.return_value = [video_stream]

        return mock_pbutils, video_info


if __name__ == "__main__":
    ut.main()
