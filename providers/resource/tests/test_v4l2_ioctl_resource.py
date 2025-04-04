import unittest as ut
from unittest.mock import MagicMock, patch, call
from v4l2_ioctl_resource import main as main_under_test
from checkbox_support.parsers.v4l2_compliance import TEST_NAME_TO_IOCTL_MAP


class TestV4L2IoctlResource(ut.TestCase):
    @patch("v4l2_ioctl_resource.sp.check_output")
    @patch("v4l2_ioctl_resource.UdevadmParser")
    def test_all_ioctl_names_are_generated(
        self, mock_udev: MagicMock, mock_check_output: MagicMock
    ):
        mock_dev_list = [MagicMock(), MagicMock()]
        for i, dev in enumerate(mock_dev_list):
            dev.name = "video{}".format(i)
            dev.category = "CAPTURE"
        mock_udev.return_value.run.return_value = mock_dev_list
        with patch("builtins.print") as mock_print:
            main_under_test()
            expected_calls = []
            for name in "video0", "video1":
                for ioctl_names in TEST_NAME_TO_IOCTL_MAP.values():
                    for ioctl_name in ioctl_names:
                        expected_calls.append(call("name: {}".format(name)))
                        expected_calls.append(
                            call("ioctl_name: {}".format(ioctl_name))
                        )
                        expected_calls.append(call())
            mock_print.assert_has_calls(expected_calls)


if __name__ == "__main__":
    ut.main()
