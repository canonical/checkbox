from os import fspath
import unittest as ut
from unittest.mock import MagicMock, call, patch
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
        bad_height = 1133222
        self._make_mock_video_info(mock_pbutils, bad_width, bad_height)

        self.assertFalse(
            validator.validate_image_dimensions(
                Path("some/path"),
                expected_height=expected_height,
                expected_width=expected_width,
            )
        )

        mock_logger.error.assert_has_calls(
            [
                call(
                    "Image width mismatch. Expected = {}, actual = {}".format(
                        expected_width, bad_width
                    )
                ),
                call(
                    "Image height mismatch. Expected = {}, actual = {}".format(
                        expected_height, bad_height
                    )
                ),
            ]
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

        bad_width = 1237219831
        bad_height = 113322
        bad_fps = 123
        bad_duration = 1

        self._make_mock_video_info(
            mock_pbutils,
            bad_width,
            bad_height,
            bad_fps,
            bad_duration,
        )

        mock_gst.SECOND = 1
        result = validator.validate_video_info(
            Path("some/path"),
            expected_width=expected_width,
            expected_height=expected_height,
            expected_fps=expected_fps,
            expected_duration_seconds=expected_duration,
            duration_tolerance_seconds=0.5,
        )
        self.assertFalse(result)

        mock_logger.error.assert_has_calls(
            [
                call(
                    "Duration not within tolerance. "
                    "Got {}s, but expected {} +- {}s".format(
                        round(bad_duration / mock_gst.SECOND, 3),
                        expected_duration,
                        0.5,
                    )
                ),
                call(
                    "Video width mismatch. Expected = {}, actual = {}".format(
                        expected_width, bad_width
                    )
                ),
                call(
                    "Video height mismatch. Expected = {}, actual = {}".format(
                        expected_height, bad_height
                    )
                ),
                call(
                    "Video FPS mismatch. Expected = {}fps, actual = {}fps".format(
                        expected_fps, bad_fps
                    )
                ),
            ]
        )

        mock_isfile.return_value = False

        result = validator.validate_video_info(
            Path("some/path"),
            expected_width=expected_width,
            expected_height=expected_height,
            expected_fps=expected_fps,
            expected_duration_seconds=expected_duration,
            duration_tolerance_seconds=0.5,
        )
        mock_logger.error.assert_called_with(
            "Video file doesn't exist at some/path"
        )

    @patch(
        "sys.argv",
        sh_split("camera_test_auto_gst_source.py take-photo -p some/dir"),
    )
    @patch("camera_test_auto_gst_source.get_devices")
    @patch("camera_test_auto_gst_source.logger")
    def test_exit_if_no_cameras(
        self,
        mock_logger: MagicMock,
        mock_get_devices: MagicMock,
    ):
        mock_get_devices.return_value = []
        import camera_test_auto_gst_source as CTAGS

        self.assertEqual(CTAGS.main(), 1)
        mock_logger.error.assert_called_with(
            "GStreamer cannot find any cameras on this device. "
            "If you know a camera element exists, then it did not implement "
            "Gst.DeviceProvider to make itself visible to GStreamer "
            "or it is inaccessible without sudo."
        )

    @patch("camera_test_auto_gst_source.get_devices")
    @patch("camera_test_auto_gst_source.cam")
    def test_encoding_arg_group(
        self, mock_cam: MagicMock, mock_get_devices: MagicMock
    ):
        import camera_test_auto_gst_source as CTAGS

        mock_resolver = MagicMock()
        mock_cam.CapsResolver.return_value = mock_resolver
        mock_resolver.get_all_fixated_caps.return_value = [MagicMock()]
        mock_get_devices.return_value = [MagicMock()]

        with patch(
            "sys.argv",
            sh_split(
                "camera_test_auto_gst_source.py record-video "
                "--encoding mp4_h264 --skip-validation"
            ),
        ):
            CTAGS.main()
            last_called_args = mock_cam.record_video.call_args[-1]
            self.assertEqual(
                last_called_args["encoding_profile"],
                CTAGS.ENCODING_PROFILES["mp4_h264"]["profile_str"],
            )
            self.assertIn(
                CTAGS.ENCODING_PROFILES["mp4_h264"]["file_extension"],
                fspath(last_called_args["file_path"]),
            )

        file_ext = "ext"
        with patch(
            "sys.argv",
            sh_split(
                "camera_test_auto_gst_source.py record-video "
                "--encoding mp4_h264 --file-extension {}".format(file_ext)
            ),
        ):
            CTAGS.main()
            last_called_args = mock_cam.record_video.call_args[-1]
            self.assertEqual(
                last_called_args["encoding_profile"],
                CTAGS.ENCODING_PROFILES["mp4_h264"]["profile_str"],
            )
            self.assertIn(
                file_ext,
                fspath(last_called_args["file_path"]),
            )

        encoding_str = "video/something, str"
        with patch(
            "sys.argv",
            sh_split(
                "camera_test_auto_gst_source.py record-video "
                + '--custom-encoding-string "{}" '.format(encoding_str)
                + "--file-extension {}".format(file_ext)
            ),
        ):
            CTAGS.main()
            last_called_args = mock_cam.record_video.call_args[-1]
            self.assertEqual(
                last_called_args["encoding_profile"],
                encoding_str,
            )
            self.assertIn(
                file_ext,
                fspath(last_called_args["file_path"]),
            )

        with patch(
            "sys.argv",
            sh_split(
                "camera_test_auto_gst_source.py record-video "
                + '--custom-encoding-string "{}" '.format(encoding_str)
            ),
        ):
            self.assertRaises(AssertionError, CTAGS.main)

    @patch(
        "sys.argv",
        sh_split("camera_test_auto_gst_source.py take-photo -p some/dir"),
    )
    @patch("os.path.isfile")
    @patch("camera_test_auto_gst_source.GstPbutils")
    @patch("camera_test_auto_gst_source.GLib")
    @patch("camera_test_auto_gst_source.logger")
    def test_handle_glib_errors(
        self,
        mock_logger: MagicMock,
        mock_glib: MagicMock,
        mock_pbutils: MagicMock,
        mock_isfile: MagicMock,
    ):
        class GError(BaseException):
            pass

        mock_glib.GError = GError
        mock_glib.Error = GError
        mock_isfile.return_value = True
        mock_discoverer = MagicMock()
        mock_discoverer.name = "bruh"
        mock_pbutils.Discoverer.return_value = mock_discoverer
        mock_discoverer.discover_uri.side_effect = GError("some message")

        import camera_test_auto_gst_source as CTAGS

        self.assertFalse(
            CTAGS.MediaValidator.validate_image_dimensions(
                Path("some/path"),
                expected_height=1,
                expected_width=1,
            ),
        )

        mock_logger.error.assert_called_with(
            "Encountered an error when attempting to read some/path. some message"
        )

        self.assertFalse(
            CTAGS.MediaValidator.validate_video_info(
                Path("some/path"),
                expected_height=1,
                expected_width=1,
                duration_tolerance_seconds=1,
                expected_duration_seconds=1,
                expected_fps=1,
            ),
        )

        mock_logger.error.assert_called_with(
            "Encountered an error when attempting to read some/path. some message"
        )

    def _make_mock_video_info(
        self,
        mock_pbutils: MagicMock,
        width,
        height,
        fps=None,
        duration=None,
    ):
        mock_pbutils.reset_mock()
        video_info = MagicMock()
        if duration is not None:
            video_info.get_duration.return_value = duration
        mock_pbutils.Discoverer.return_value = MagicMock()

        mock_pbutils.Discoverer().discover_uri.return_value = video_info
        video_stream = MagicMock()
        video_stream.get_width.return_value = width
        video_stream.get_height.return_value = height

        if fps is not None:
            video_stream.get_framerate_num.return_value = fps

        video_info.get_video_streams.return_value = [video_stream]

        return mock_pbutils, video_info


if __name__ == "__main__":
    ut.main()
