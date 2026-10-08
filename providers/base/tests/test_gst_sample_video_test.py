import subprocess
import unittest
from unittest.mock import patch

import gst_sample_video_test as gsvt


class ParseArgsTests(unittest.TestCase):
    def test_positive_timeout(self):
        self.assertEqual(gsvt.parse_args(["5"]).timeout, 5)

    def test_rejects_non_positive_timeout(self):
        for value in ["0", "-1", "abc"]:
            with self.subTest(value=value):
                with patch("sys.stderr"), self.assertRaises(SystemExit):
                    gsvt.parse_args([value])


class ElementExistsTests(unittest.TestCase):
    @patch("subprocess.call", return_value=0)
    def test_exists(self, mock_call):
        self.assertTrue(gsvt.element_exists("xvimagesink"))
        self.assertEqual(
            mock_call.call_args[0][0],
            ["gst-inspect-1.0", "--exists", "xvimagesink"],
        )

    @patch("subprocess.call", return_value=1)
    def test_missing(self, mock_call):
        self.assertFalse(gsvt.element_exists("waylandsink"))


class FirstAvailableTests(unittest.TestCase):
    @patch("gst_sample_video_test.element_exists", return_value=True)
    def test_returns_first_candidate(self, mock_exists):
        self.assertEqual(gsvt.first_available(["a", "b"]), "a")

    @patch("gst_sample_video_test.element_exists")
    def test_falls_back_to_next_candidate(self, mock_exists):
        mock_exists.side_effect = lambda name: name == "b"
        self.assertEqual(gsvt.first_available(["a", "b"]), "b")

    @patch("gst_sample_video_test.element_exists", return_value=False)
    def test_none_available(self, mock_exists):
        with self.assertRaises(SystemExit):
            gsvt.first_available(["a", "b"])


class PickSinkTests(unittest.TestCase):
    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    @patch("gst_sample_video_test.element_exists", return_value=True)
    def test_wayland_prefers_waylandsink(self, mock_exists):
        self.assertEqual(gsvt.pick_sink(), "waylandsink")

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    @patch("gst_sample_video_test.element_exists")
    def test_wayland_falls_back_to_glimagesink(self, mock_exists):
        mock_exists.side_effect = lambda name: name == "glimagesink"
        self.assertEqual(gsvt.pick_sink(), "glimagesink")

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    @patch("gst_sample_video_test.element_exists", return_value=True)
    def test_x11_prefers_xvimagesink(self, mock_exists):
        self.assertEqual(gsvt.pick_sink(), "xvimagesink")

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    @patch("gst_sample_video_test.element_exists")
    def test_x11_falls_back_to_glimagesink(self, mock_exists):
        mock_exists.side_effect = lambda name: name == "glimagesink"
        self.assertEqual(gsvt.pick_sink(), "glimagesink")

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    @patch("gst_sample_video_test.element_exists", return_value=False)
    def test_no_sink_available(self, mock_exists):
        with self.assertRaises(SystemExit):
            gsvt.pick_sink()

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "tty"})
    def test_non_graphical_session(self):
        with self.assertRaises(SystemExit):
            gsvt.pick_sink()

    @patch.dict("os.environ", {}, clear=True)
    def test_session_type_unset(self):
        with self.assertRaises(SystemExit):
            gsvt.pick_sink()


@patch("gst_sample_video_test.element_exists", return_value=True)
@patch("gst_sample_video_test.pick_sink", return_value="xvimagesink")
@patch("sys.stdout")
class MainTests(unittest.TestCase):
    @patch(
        "subprocess.check_call",
        side_effect=subprocess.TimeoutExpired("x", 2),
    )
    def test_timeout_is_pass(
        self, mock_call, mock_stdout, mock_pick, mock_exists
    ):
        self.assertEqual(gsvt.main(["2"]), 0)
        mock_call.assert_called_once_with(
            [
                "gst-launch-1.0",
                "-v",
                "videotestsrc",
                "!",
                "videoconvert",
                "!",
                "xvimagesink",
            ],
            timeout=2,
        )

    @patch(
        "subprocess.check_call",
        side_effect=subprocess.CalledProcessError(3, "x"),
    )
    def test_pipeline_error_is_fail(
        self, mock_call, mock_stdout, mock_pick, mock_exists
    ):
        self.assertEqual(gsvt.main(["2"]), 3)

    @patch("subprocess.check_call", return_value=0)
    def test_pipeline_exits_by_itself(
        self, mock_call, mock_stdout, mock_pick, mock_exists
    ):
        self.assertEqual(gsvt.main(["2"]), 0)

    @patch("subprocess.check_call", return_value=0)
    def test_falls_back_to_ffmpegcolorspace(
        self, mock_call, mock_stdout, mock_pick, mock_exists
    ):
        mock_exists.side_effect = lambda name: name == "ffmpegcolorspace"
        gsvt.main(["2"])
        self.assertIn("ffmpegcolorspace", mock_call.call_args[0][0])
        self.assertNotIn("videoconvert", mock_call.call_args[0][0])
