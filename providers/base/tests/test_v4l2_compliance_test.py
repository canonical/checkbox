import unittest as ut
from unittest.mock import MagicMock, call, patch
from v4l2_compliance_test import main as main_under_test
from shlex import split as sh_split


class TestV4L2ComplianceTest(ut.TestCase):

    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_failed_query_cap(self, mock_parser: MagicMock):
        with patch(
            "sys.argv",
            [
                "v4l2_compliance_test.py",
                "--include",
                "VIDIOC_QUERYCAP",
                "--device",
                "/dev/video0",
            ],
        ):
            # query cap failure should always fail the test case
            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    "failed": ["VIDIOC_QUERYCAP"],
                    "not_supported": [],
                },
            )

            self.assertRaises(SystemExit, main_under_test)

        with patch(
            "sys.argv",
            [
                "v4l2_compliance_test.py",
                "--include",
                "VIDIOC_ENUM_FMT",
                "--device",
                "/dev/video0",
            ],
        ):
            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    "failed": ["VIDIOC_QUERYCAP", "VIDIOC_ENUM_FMT"],
                    "not_supported": [],
                },
            )
            # also fail even if query cap is not listed in the args
            self.assertRaises(SystemExit, main_under_test)

    @patch(
        "sys.argv",
        ["v4l2_compliance_test.py", "--device", "/dev/video1"],
    )
    @patch("sys.stderr")
    @patch("builtins.print")
    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_report_correct_failures(
        self,
        mock_parser: MagicMock,
        mock_print: MagicMock,
        mock_stderr: MagicMock,
    ):
        mock_parser.return_value = (
            {},
            {
                "succeeded": [],
                "failed": ["VIDIOC_ENUM_FMT"],
                "not_supported": [],
            },
        )

        self.assertRaises(SystemExit, main_under_test)
        mock_print.assert_called_with(
            mock_parser.return_value[1]["failed"],
            "failed the test",
            file=mock_stderr,
        )

        mock_print.reset_mock()
        mock_parser.return_value = (
            {},
            {
                "succeeded": [],
                "failed": ["VIDIOC_QUERYCTRL"],
                "not_supported": [],
            },
        )

        self.assertRaises(SystemExit, main_under_test)
        mock_print.assert_called_with(
            mock_parser.return_value[1]["failed"],
            "failed the test",
            file=mock_stderr,
        )

        mock_print.reset_mock()
        mock_parser.return_value = (
            {},
            {
                "succeeded": [],
                "failed": ["VIDIOC_QUERYCTRL", "VIDIOC_ENUM_FMT"],
                "not_supported": [],
            },
        )

        self.assertRaises(SystemExit, main_under_test)
        mock_print.assert_called_with(
            mock_parser.return_value[1]["failed"],
            "failed the test",
            file=mock_stderr,
        )

    @patch(
        "sys.argv",
        sh_split(
            "v4l2_compliance_test.py "
            + "--include VIDOC_G_FMT --device /dev/video1 "
            + "--treat-unsupported-as-fail"
        ),
    )
    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_treat_unsupported_as_fail(
        self,
        mock_parser: MagicMock,
    ):
        mock_parser.return_value = (
            {},
            {
                "succeeded": [],
                "failed": [],
                "not_supported": ["VIDOC_G_FMT"],
            },
        )

        self.assertRaises(SystemExit, main_under_test)


if __name__ == "__main__":
    ut.main()
