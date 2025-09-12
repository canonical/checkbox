import unittest as ut
from unittest.mock import MagicMock, call, patch

from v4l2_compliance_test import main as main_under_test


class TestV4L2ComplianceTest(ut.TestCase):

    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_failed_query_cap(self, mock_parser: MagicMock):
        with patch(
            "sys.argv",
            [
                "v4l2_compliance_test.py",
                "--ioctl-selection",
                "blockers",
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
                "--ioctl-selection",
                "blockers",
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

    @patch("builtins.print")
    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_report_correct_failures(
        self,
        mock_parser: MagicMock,
        mock_print: MagicMock,
    ):
        with patch(
            "sys.argv",
            [
                "v4l2_compliance_test.py",
                "--ioctl-selection",
                "non-blockers",
                "--device",
                "/dev/video0",
            ],
        ):
            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    "failed": ["VIDIOC_DECODER_CMD"],
                    "not_supported": [],
                },
            )
            self.assertRaises(SystemExit, main_under_test)
            mock_print.assert_has_calls(
                [
                    call(
                        " - {}".format(ioctl_name),
                    )
                    for ioctl_name in mock_parser.return_value[1]["failed"]
                ],
                any_order=True,
            )

            mock_print.reset_mock()

            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    "failed": ["VIDIOC_DECODER_CMD"],
                    "not_supported": [],
                },
            )
            self.assertRaises(SystemExit, main_under_test)
            mock_print.assert_has_calls(
                [
                    call(
                        " - {}".format(ioctl_name),
                    )
                    for ioctl_name in mock_parser.return_value[1]["failed"]
                ],
                any_order=True,
            )

            mock_print.reset_mock()

            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    "failed": ["VIDIOC_ENUM_FMT", "VIDIOC_DECODER_CMD"],
                    "not_supported": [],
                },
            )
            self.assertRaises(SystemExit, main_under_test)
            mock_print.assert_has_calls(
                [
                    call(
                        " - {}".format(ioctl_name),
                    )
                    for ioctl_name in mock_parser.return_value[1]["failed"]
                ],
                any_order=True,
            )

        with patch(
            "sys.argv",
            [
                "v4l2_compliance_test.py",
                "--ioctl-selection",
                "all",
                "--device",
                "/dev/video0",
            ],
        ):
            mock_print.reset_mock()
            mock_parser.return_value = (
                {},
                {
                    "succeeded": [],
                    # 1 blocker, 1 non-blocker
                    "failed": ["VIDIOC_REQBUFS", "VIDIOC_DECODER_CMD"],
                    "not_supported": [],
                },
            )
            self.assertRaises(SystemExit, main_under_test)
            mock_print.assert_has_calls(
                [
                    call(
                        " - {}".format(ioctl_name),
                    )
                    for ioctl_name in mock_parser.return_value[1]["failed"]
                ],
                any_order=True,
            )

    @patch(
        "sys.argv",
        [
            "v4l2_compliance_test.py",
            "--ioctl-selection",
            "non-blockers",
            "--device",
            "/dev/video0",
            "--treat-unsupported-as-fail",
        ],
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
                "not_supported": ["VIDIOC_G_FMT"],
            },
        )

        self.assertRaises(SystemExit, main_under_test)

    @patch(
        "sys.argv",
        [
            "v4l2_compliance_test.py",
            "--ioctl-selection",
            "blockers",
            "--device",
            "/dev/video0",
        ],
    )
    @patch("v4l2_compliance_test.get_release_info")
    @patch("builtins.print")
    @patch("v4l2_compliance_test.parse_v4l2_compliance")
    def test_18_22_workaround(
        self,
        mock_parser: MagicMock,
        mock_print: MagicMock,
        mock_get_release_info: MagicMock,
    ):
        # this test is only intended for the temp workaround for 18 and 22
        # VIDOC_REQBUFS is skipped on these 2 versions
        mock_parser.return_value = (
            {},
            {
                "succeeded": ["VIDIOC_QUERYCAP"],
                "failed": ["VIDIOC_REQBUFS"],
                "not_supported": [],
            },
        )
        mock_get_release_info.return_value = {"codename": "jammy"}
        main_under_test()
        mock_print.assert_has_calls(
            [call("No failed IOCTLs detected")],
            any_order=True,
        )


if __name__ == "__main__":
    ut.main()
