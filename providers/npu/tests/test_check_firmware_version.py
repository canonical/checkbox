#!/usr/bin/env python3
import unittest
import io
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest

import check_firmware_version


class TestVersionPattern(unittest.TestCase):
    def test_date_format_numeric(self):
        line = "20240101*v1.0.0"
        self.assertIsNotNone(
            check_firmware_version.VERSION_PATTERN.match(line)
        )

    def test_date_format_text(self):
        line = "Jan  1 2024*v1.0.0"
        self.assertIsNotNone(
            check_firmware_version.VERSION_PATTERN.match(line)
        )

    def test_date_format_text_double_digit(self):
        line = "Feb 12 2024*v1.0.0"
        self.assertIsNotNone(
            check_firmware_version.VERSION_PATTERN.match(line)
        )

    def test_no_match(self):
        line = "This is a regular log line."
        self.assertIsNone(check_firmware_version.VERSION_PATTERN.match(line))

    def test_partial_match(self):
        line = "20240101 v1.0.0"
        self.assertIsNone(check_firmware_version.VERSION_PATTERN.match(line))

    def test_previous_releases(self):
        """
        Checks that the regex matches all past release strings until Sept 2025
        """
        previous_releases = [
            "20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee",
            "Sep 25 2025*NPU40xx*build/ci/npu-fw-ci-ci_branch_UD202538_PTL_PV_npu_release_25ww35-20250915_222036-29036-1-g2485cfeafee*2485cfeafeed591eaa9a320bfae2407c1b83b29f",
            "20250723*MTL_CLIENT_SILICON-NVR+NN-deployment*52e7ebee50a93a07d14a1f162226cd55ad3999f0*52e7ebee50a93a07d14a1f162226cd55ad3999f0*52e7ebee50a",
            "Jul 23 2025*NPU40xx*build/ci/npu-fw-ci-main-20250721_233537-27032-2-g52e7ebee50a*52e7ebee50a93a07d14a1f162226cd55ad3999f0",
            "20250627*MTL_CLIENT_SILICON-NVR+NN-deployment*2fc7252521edea4e75ec14e475a72ba6f0f92685*2fc7252521edea4e75ec14e475a72ba6f0f92685*2fc7252521e",
            "Jun 27 2025*NPU40xx*ci_tag_ud202528_vpu_rc_20250626_1901*2fc7252521edea4e75ec14e475a72ba6f0f92685",
            "20250611*MTL_CLIENT_SILICON-NVR+NN-deployment*5437076a64c995fd1fbe21c3019f522b56db98f9*5437076a64c995fd1fbe21c3019f522b56db98f9*5437076a64c",
            "Jun 11 2025*NPU40xx*build/ci/npu-fw-ci-ci_branch_UD202524_npu_release_25ww22-20250603_183038-26415-8-g5437076a64c*5437076a64c995fd1fbe21c3019f522b56db98f9",
            "20250415*MTL_CLIENT_SILICON-release*1900*ci_tag_ud202518_vpu_rc_20250415_1900*7ef0f3fdb82",
            "Apr 15 2025*NPU40xx*ci_tag_ud202518_vpu_rc_20250415_1900*7ef0f3fdb8257a43805f207ecf13491d98963d4f",
            "20250306*MTL_CLIENT_SILICON-release*1130*ci_tag_ud202512_vpu_rc_20250306_1130*5064b5debc3",
            "Mar 6 2025*NPU40xx*ci_tag_ud202512_vpu_rc_20250306_1130*5064b5debc377e1c4b74f69dc14e2e536dba393d",
            "20250115*MTL_CLIENT_SILICON-release*1905*ci_tag_ud202504_vpu_rc_20250115_1905*ae83b65d01c",
            "Jan 15 2025*NPU40xx*ci_tag_ud202504_vpu_rc_20250115_1905*ae83b65d01ccb4696594af0cafffea50a52520da",
            "20241025*MTL_CLIENT_SILICON-release*1830*ci_tag_ud202444_vpu_rc_20241025_1830*ae072b315bc",
            "Oct 25 2024*NPU40xx*ci_tag_ud202444_vpu_eng_20241025_1500*ae072b315bc135fb4cc60cfa758b2a926bd6498f",
            "20241025*MTL_CLIENT_SILICON-release*1830*ci_tag_ud202444_vpu_rc_20241025_1830*ae072b315bc",
            "Oct 25 2024*NPU40xx*ci_tag_ud202444_vpu_eng_20241025_1500*ae072b315bc135fb4cc60cfa758b2a926bd6498f",
            "20240820*MTL_CLIENT_SILICON-release*1902*ci_tag_ud202436_vpu_rc_20240820_1902*a4634b5107c",
            "Aug 20 2024*LNL*ci_tag_ud202436_vpu_rc_20240820_1902*a4634b5107c7ded2bbfa7d198e37088ec258749a",
            "20240726*MTL_CLIENT_SILICON-release*0004*ci_tag_ud202428_vpu_rc_20240726_0004*e4a99ed6b3e",
            "Jul 26 2024*LNL*ci_tag_ud202428_vpu_rc_20240726_0004*e4a99ed6b3e2e6c5a6e920cfa427bb4db2547c13",
            "20240611*MTL_CLIENT_SILICON-release*0003*ci_tag_ud202424_vpu_rc_20240611_0003*f3e8a8f2747",
            "Jun 11 2024*LNL*ci_tag_ud202424_vpu_rc_20240611_0003*f3e8a8f27471d4127d8d92a8dc679b861ef43e43",
            "20240611*MTL_CLIENT_SILICON-release*0003*ci_tag_ud202424_vpu_rc_20240611_0003*f3e8a8f2747",
            "Jun 11 2024*LNL*ci_tag_ud202424_vpu_rc_20240611_0003*f3e8a8f27471d4127d8d92a8dc679b861ef43e43",
        ]

        for version_string in previous_releases:
            self.assertIsNotNone(
                check_firmware_version.VERSION_PATTERN.match(version_string)
            )


class TestGetActiveFirmwareLine(unittest.TestCase):
    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("subprocess.run")
    def test_success_single_match(self, mock_run, mock_stderr):
        mock_stdout = "line 1\nSome log about intel_vpu\nFirmware: intel/vpu foo bar\nline 4"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout
        )

        result = check_firmware_version.get_active_firmware_line()

        self.assertEqual(result, "Firmware: intel/vpu foo bar")
        mock_run.assert_called_with(
            ["journalctl", "--dmesg"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        self.assertEqual(mock_stderr.getvalue(), "")

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("subprocess.run")
    def test_success_multiple_matches(self, mock_run, mock_stderr):
        """Test finding multiple lines (should return the last one)."""
        mock_stdout = "line 1\nFirmware: intel/vpu old_version\nline 2\nFirmware: intel/vpu new_version"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout
        )

        result = check_firmware_version.get_active_firmware_line()
        self.assertEqual(result, "Firmware: intel/vpu new_version")

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("subprocess.run")
    def test_no_match_found(self, mock_run, mock_stderr):
        """Test when no matching lines are found."""
        mock_stdout = "line 1\nline 2\nline 3"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout
        )

        with pytest.raises(
            SystemExit, match="No 'intel_vpu' firmware logs found in dmesg."
        ):
            check_firmware_version.get_active_firmware_line()


class TestFindVersionInFile(unittest.TestCase):
    @patch("subprocess.run")
    def test_success_finds_first_match(self, mock_run):
        """Test finding the first version string even if there's multiple in the fw file."""
        mock_stdout = "some strings\nmore strings\n20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee\n20250115*MTL_CLIENT_SILICON-release*1905*ci_tag_ud202504_vpu_rc_20250115_1905*ae83b65d01c"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout
        )

        dummy_path = Path("/fake/fw.bin")
        result = check_firmware_version.find_version_in_file(dummy_path)

        self.assertEqual(
            result,
            "20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee",
        )
        mock_run.assert_called_with(
            ["strings", dummy_path],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )

    @patch("subprocess.run")
    def test_no_match(self, mock_run):
        """Test when 'strings' runs but no version string is found."""
        mock_stdout = "strings\nmore strings\neven more strings\nthis definitely doesn't match anything"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout
        )

        result = check_firmware_version.find_version_in_file(
            Path("/fake/fw.bin")
        )
        self.assertIsNone(result)

    @patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")
    )
    def test_subprocess_error(self, mock_run):
        """Test when 'strings' command fails."""
        result = check_firmware_version.find_version_in_file(
            Path("/fake/fw.bin")
        )
        self.assertIsNone(result)


class TestMainFunction(unittest.TestCase):
    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch(
        "check_firmware_version.FIRMWARE_SEARCH_DIR", new_callable=MagicMock
    )
    @patch("check_firmware_version.find_version_in_file")
    @patch("check_firmware_version.get_active_firmware_line")
    def test_main_success(
        self,
        mock_get_line,
        mock_find_version,
        mock_fw_dir,
        mock_stdout,
        mock_stderr,
    ):
        active_line = "[   14.967341] intel_vpu 0000:00:0b.0: [drm] Firmware: intel/vpu/vpu_37xx_v1.bin, version: 20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee"

        mock_get_line.return_value = active_line

        mock_fw_dir.is_dir.return_value = True

        mock_fw_bin = MagicMock(spec=Path)
        mock_fw_bin.is_file.return_value = True
        mock_fw_bin.suffix = ".bin"

        mock_other_file = MagicMock(spec=Path)
        mock_other_file.is_file.return_value = True
        mock_other_file.suffix = ".txt"

        mock_fw_dir.iterdir.return_value = [mock_other_file, mock_fw_bin]

        driver_version = "20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee"
        mock_find_version.return_value = driver_version

        return_code = check_firmware_version.main()

        mock_get_line.assert_called_once()
        mock_fw_dir.is_dir.assert_called_once()
        mock_find_version.assert_called_once_with(mock_fw_bin)
        self.assertIn("Test success", mock_stdout.getvalue())
        self.assertIn(driver_version, mock_stdout.getvalue())
        self.assertEqual(mock_stderr.getvalue(), "")

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch(
        "check_firmware_version.FIRMWARE_SEARCH_DIR", new_callable=MagicMock
    )
    @patch("check_firmware_version.find_version_in_file")
    @patch("check_firmware_version.get_active_firmware_line")
    def test_main_fail_no_match(
        self,
        mock_get_line,
        mock_find_version,
        mock_fw_dir,
        mock_stdout,
        mock_stderr,
    ):
        active_line = "[   14.967341] intel_vpu 0000:00:0b.0: [drm] Firmware: intel/vpu/vpu_37xx_v1.bin, version: 20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee"

        mock_get_line.return_value = active_line

        mock_fw_dir.is_dir.return_value = True

        mock_fw_bin = MagicMock(spec=Path)
        mock_fw_bin.is_file.return_value = True
        mock_fw_bin.suffix = ".bin"
        mock_fw_dir.iterdir.return_value = [mock_fw_bin]

        # Return a *different* version from the file
        driver_version = "20241025*MTL_CLIENT_SILICON-release*1830*ci_tag_ud202444_vpu_rc_20241025_1830*ae072b315bc"
        mock_find_version.return_value = driver_version

        with pytest.raises(
            SystemExit,
            match="The loaded firmware does not "
            "match any version in the snap files.",
        ):
            check_firmware_version.main()

        self.assertEqual(mock_stdout.getvalue(), "")

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch(
        "check_firmware_version.FIRMWARE_SEARCH_DIR", new_callable=MagicMock
    )
    @patch("check_firmware_version.find_version_in_file")
    @patch("check_firmware_version.get_active_firmware_line")
    def test_main_fail_no_active_line(
        self,
        mock_get_line,
        mock_find_version,
        mock_fw_dir,
        mock_stdout,
        mock_stderr,
    ):
        # make get_active_firmware_line fail
        mock_get_line.return_value = None

        with pytest.raises(
            SystemExit,
            match="The loaded firmware does not "
            "match any version in the snap files.",
        ):
            check_firmware_version.main()

        self.assertEqual(mock_stdout.getvalue(), "")

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch(
        "check_firmware_version.FIRMWARE_SEARCH_DIR", new_callable=MagicMock
    )
    @patch("check_firmware_version.find_version_in_file")
    @patch("check_firmware_version.get_active_firmware_line")
    def test_main_fail_no_directory(
        self,
        mock_get_line,
        mock_find_version,
        mock_fw_dir,
        mock_stdout,
        mock_stderr,
    ):
        """Test when the snap firmware directory doesn't exist (maybe snap not installed or defect)."""
        mock_get_line.return_value = "[ 123.967341] intel_vpu 0000:00:0b.0: [drm] Firmware: intel/vpu/vpu_37xx_v1.bin, version: 20250925*MTL_CLIENT_SILICON-NVR+NN-deployment*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafeed591eaa9a320bfae2407c1b83b29f*2485cfeafee"
        # Directory not found
        mock_fw_dir.is_dir.return_value = False

        with pytest.raises(SystemExit, match="Firmware directory not found."):
            check_firmware_version.main()

        mock_find_version.assert_not_called()
        self.assertEqual(mock_stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
