import unittest
import os
import json
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
        journal_json = [
            {
                "__CURSOR": "s=46b97576da5143dbb410415da6525b06",
                "_RUNTIME_SCOPE": "system",
                "_BOOT_ID": "696f60fdf66d4ec2958cb03122ecd4f3",
                "MESSAGE": "Linux version 6.11.0-21-generic (buildd@lcy02-amd64-097) (x86_64-linux-gnu-gcc-13 (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0, GNU ld (GNU Binutils for Ubuntu) 2.42) #21~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Mon Feb 24 16:52:15 UTC 2 (Ubuntu 6.11.0-21.21~24.04.1-generic 6.11.11)",
                "SYSLOG_FACILITY": "0",
                "_TRANSPORT": "kernel",
                "PRIORITY": "5",
                "__REALTIME_TIMESTAMP": "1743490675360781",
                "__SEQNUM": "335299",
                "_SOURCE_MONOTONIC_TIMESTAMP": "0",
                "_MACHINE_ID": "622e508e145d4bfd866225e3ec442a15",
                "__SEQNUM_ID": "46b97576da5143dbb410415da6525b06",
                "__MONOTONIC_TIMESTAMP": "5338187",
                "_HOSTNAME": "test",
                "SYSLOG_IDENTIFIER": "kernel",
            },
            {
                "__SEQNUM_ID": "46b97576da5143dbb410415da6525b06",
                "__MONOTONIC_TIMESTAMP": "5338200",
                "_BOOT_ID": "696f60fdf66d4ec2958cb03122ecd4f3",
                "_HOSTNAME": "test",
                "_SOURCE_MONOTONIC_TIMESTAMP": "0",
                "PRIORITY": "6",
                "__CURSOR": "s=46b97576da5143dbb410415da6525b06",
                "SYSLOG_FACILITY": "0",
                "__SEQNUM": "335300",
                "__REALTIME_TIMESTAMP": "1743490675360794",
                "_RUNTIME_SCOPE": "system",
                "SYSLOG_IDENTIFIER": "kernel",
                "_MACHINE_ID": "622e508e145d4bfd866225e3ec442a15",
                "_TRANSPORT": "kernel",
                "MESSAGE": "Command line: BOOT_IMAGE=/boot/vmlinuz-6.11.0-21-generic root=UUID=e2679ed2-f0ba-4f9e-992d-84cb5fa40795 ro quiet splash vt.handoff=7",
            },
        ]

        # When used with --output json, journalctl outputs one json object per
        # line. Reconstructing it as it originally appears...
        mock_sb_co.return_value = "\n".join(
            [json.dumps(msg) for msg in journal_json]
        )
        linux_version = get_kernel_version_from_journal("")
        self.assertEqual(linux_version, "6.11.0-21-generic")

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

        main()
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
        mock_gkvfj.side_effect = ["6.11.0-19-generic", "5.14", "5.14"]
        mock_gbi.return_value = ["1", "2"]

        main()
        mock_ce.assert_not_called()
        mock_print.assert_called_once_with(
            "No microcode software errors detected."
        )
