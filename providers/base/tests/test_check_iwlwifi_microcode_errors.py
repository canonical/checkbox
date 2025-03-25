import unittest
import os
from unittest.mock import patch
from check_iwlwifi_microcode_errors import (
    get_boot_ids,
    get_kernel_version_from_journal,
    check_error,
    main,
)


class TestCheckIwlwifi(unittest.TestCase):
    @patch("check_iwlwifi_microcode_errors.subprocess.check_output")
    def test_get_boot_ids_ok(self, mock_sb_co):
        mock_sb_co.return_value = (
            '[{"index":-1,"boot_id":"1","first_entry":1,"last_entry":2},'
            '{"index":0,"boot_id":"2","first_entry":3,"last_entry":4}]'
        )
        boot_ids = get_boot_ids()
        self.assertEqual(len(boot_ids), 2)
        self.assertIn("1", boot_ids)
        self.assertIn("2", boot_ids)

    @patch("check_iwlwifi_microcode_errors.subprocess.check_output")
    def test_get_kernel_version_from_journal(self, mock_sb_co):
        mock_sb_co.return_value = (
            '{"PRIORITY":"5","_MACHINE_ID":"1","_SOURCE_MONOTONIC_TIMESTAMP":'
            '"0","MESSAGE":"Linux version 6.11.0-19-generic '
            "(buildd@lcy02-amd64-014) (x86_64-linux-gnu-gcc-13 "
            "(Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0, GNU ld (GNU Binutils for "
            "Ubuntu) 2.42) #19~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Mon Feb 17 "
            '11:51:52 UTC 2 (Ubuntu 6.11.0-19.19~24.04.1-generic 6.11.11)",'
            '"_BOOT_ID":"1","__MONOTONIC_TIMESTAMP":"1","__CURSOR":"test",'
            '"_TRANSPORT":"kernel","SYSLOG_IDENTIFIER":"kernel",'
            '"__SEQNUM_ID":"1","_RUNTIME_SCOPE":"system",'
            '"SYSLOG_FACILITY":"0","__REALTIME_TIMESTAMP":"1",'
            '"_HOSTNAME":"test","__SEQNUM":"1"}\n'
        )
        linux_version = get_kernel_version_from_journal("")
        self.assertEqual(linux_version, "6.11.0-19-generic")

    @patch("check_iwlwifi_microcode_errors.subprocess.check_output")
    def test_check_error_none(self, mock_sb_co):
        mock_sb_co.return_value = "line1\nline2"
        check_error("1")

    @patch("check_iwlwifi_microcode_errors.subprocess.check_output")
    def test_check_error_found(self, mock_sb_co):
        mock_sb_co.return_value = "line1\nMicrocode SW error detected\nline3"
        with self.assertRaisesRegex(
            SystemExit, "error detected during boot 1"
        ):
            check_error("1")

    @patch("check_iwlwifi_microcode_errors.get_boot_ids")
    @patch("check_iwlwifi_microcode_errors.get_kernel_version_from_journal")
    @patch("check_iwlwifi_microcode_errors.check_error")
    @patch("builtins.print")
    def test_main_ok(self, mock_print, mock_ce, mock_gkvfj, mock_gbi):
        mock_gkvfj.return_value = "6.11.0-19-generic"
        mock_gbi.return_value = ["1", "2"]

        main("6.11.0-19-generic")
        mock_ce.assert_any_call("1")
        mock_ce.assert_any_call("2")
        mock_print.assert_called_once_with(
            "No microcode software errors detected."
        )

    @patch("check_iwlwifi_microcode_errors.get_boot_ids")
    @patch("check_iwlwifi_microcode_errors.get_kernel_version_from_journal")
    @patch("check_iwlwifi_microcode_errors.check_error")
    @patch("builtins.print")
    def test_main_no_check(self, mock_print, mock_ce, mock_gkvfj, mock_gbi):
        mock_gkvfj.return_value = "5.14"
        mock_gbi.return_value = ["1", "2"]

        main("6.11.0-19-generic")
        mock_ce.assert_not_called()
        mock_print.assert_called_once_with(
            "No microcode software errors detected."
        )
