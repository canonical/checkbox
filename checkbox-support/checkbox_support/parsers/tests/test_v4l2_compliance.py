import subprocess as sp
from checkbox_support.parsers.v4l2_compliance import parse_v4l2_compliance
import unittest as ut
from unittest.mock import patch, MagicMock

try:
    # new in python 3.9
    from importlib.resources import files

    def read_file_as_str(name: str):
        resource_path = "parsers/tests/v4l2_compliance_data/{}.txt".format(
            name
        )
        ref = files("checkbox_support")
        file_ref = ref.joinpath(resource_path)
        with file_ref.open("r") as f:
            return f.read()

except ImportError:
    # 3.5 fallback
    from pkg_resources import resource_filename

    def read_file_as_str(name: str):
        resource = "parsers/tests/v4l2_compliance_data/{}.txt".format(name)
        filename = resource_filename("checkbox_support", resource)
        with open(filename) as f:
            return f.read()


class TestV4L2ComplianceParser(ut.TestCase):

    @patch("subprocess.run")
    def test_happy_path(self, mock_run: MagicMock):
        ok_input = read_file_as_str("22_04_success")
        mock_run.return_value = sp.CompletedProcess(
            [], 1, stdout=ok_input, stderr=""
        )
        summary, detail = parse_v4l2_compliance()
        self.assertDictEqual(
            {
                "device_name": "uvcvideo device /dev/video0",
                "total": 46,
                "succeeded": 43,
                "failed": 3,
                "warnings": 1,
            },
            summary,
        )
        expected_failures = read_file_as_str(
            "22_04_expected_fail_1"
        ).splitlines()
        for ioctl_request in expected_failures:
            self.assertIn(ioctl_request.strip(), detail["failed"])
        self.assertEqual(len(expected_failures), len(detail["failed"]))

    @patch("subprocess.run")
    def test_happy_path_24_04(self, mock_run: MagicMock):
        ok_input = read_file_as_str("24_04_success")
        mock_run.return_value = sp.CompletedProcess(
            [], 1, stdout=ok_input, stderr=""
        )
        summary, detail = parse_v4l2_compliance()
        self.assertDictEqual(
            {
                "device_name": "v4l2 loopback device /dev/video0",
                "total": 46,
                "succeeded": 41,
                "failed": 5,
                "warnings": 6,
            },
            summary,
        )
        expected_failures = read_file_as_str(
            "24_04_expected_fail_1"
        ).splitlines()
        for ioctl_request in expected_failures:
            self.assertIn(ioctl_request.strip(), detail["failed"])
        self.assertEqual(len(expected_failures), len(detail["failed"]))

    @patch("subprocess.run")
    def test_happy_path_18_04(self, mock_run: MagicMock):
        ok_input = read_file_as_str("18_04_success")
        mock_run.return_value = sp.CompletedProcess(
            [], 1, stdout=ok_input, stderr=""
        )
        summary, detail = parse_v4l2_compliance()
        self.assertDictEqual(
            {
                "device_name": "device /dev/video0",
                "total": 43,
                "succeeded": 38,
                "failed": 5,
                "warnings": 1,
            },
            summary,
        )
        expected_failures = read_file_as_str(
            "18_04_expected_fail_1"
        ).splitlines()
        for ioctl_request in expected_failures:
            self.assertIn(ioctl_request.strip(), detail["failed"])
        self.assertEqual(len(expected_failures), len(detail["failed"]))

    @patch("subprocess.run")
    def test_unparsable(self, mock_run: MagicMock):
        bad_input = "askdjhasjkdhlakbbeqmnwbeqmvykudsuchab,b1231"
        mock_run.return_value = sp.CompletedProcess(
            [], 1, stdout=bad_input, stderr=""
        )

        self.assertRaises(AssertionError, parse_v4l2_compliance)

    @patch("subprocess.run")
    def test_unopenable_device(self, mock_run: MagicMock):
        err_messages = [
            # 16.04 18.04: found this message in VMs
            # without camera USB pass through
            "Failed to open device /dev/video0: No such file or directory"
            # 20.04: found this msg in VMs without camera pass through
            # 22.04, 24.04: found this message if we disable camera in BIOS
            "Cannot open device /dev/video0, exiting."
        ]
        for err_msg in err_messages:
            mock_run.return_value = sp.CompletedProcess(
                [], 1, stdout="", stderr=err_msg
            )
            self.assertRaises(FileNotFoundError, parse_v4l2_compliance)


if __name__ == "__main__":
    ut.main()
