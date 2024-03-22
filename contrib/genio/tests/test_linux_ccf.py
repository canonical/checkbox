import unittest
from unittest.mock import patch, MagicMock
import linux_ccf as ccf


class TestLinuxCCF(unittest.TestCase):
    @patch("linux_ccf.subprocess.run")
    def test_runcmd(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="output", stderr="error", returncode=0
        )
        result = ccf.runcmd("echo Hello")
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.stderr, "error")
        self.assertEqual(result.returncode, 0)

    @patch("linux_ccf.PLAINBOX_SESSION_SHARE", "/share")
    @patch("linux_ccf.PLAINBOX_PROVIDER_DATA", "/tmp")
    def test_check_env_variables(self):
        self.assertEqual(ccf.check_env_variables(), None)

    @patch("linux_ccf.PLAINBOX_SESSION_SHARE", "")
    @patch("linux_ccf.PLAINBOX_PROVIDER_DATA", "/tmp")
    def test_check_session_share_not_defined(self):
        with self.assertRaises(SystemExit):
            ccf.check_env_variables()

    @patch("linux_ccf.PLAINBOX_SESSION_SHARE", "/share")
    @patch("linux_ccf.PLAINBOX_PROVIDER_DATA", "")
    def test_check_provider_data_not_defined(self):
        with self.assertRaises(SystemExit):
            ccf.check_env_variables()

    @patch("linux_ccf.runcmd")
    def test_test_linux_ccf(self, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(returncode=0),
            MagicMock(
                stdout="[-] Success, all clocks are mapped !",
                stderr="",
                returncode=0,
            ),
        ]
        ccf.test_linux_ccf("mt8390")
        mock_runcmd.assert_called()

    def test_test_linux_ccf_fails_with_mt8365(self):
        with self.assertRaises(SystemExit):
            ccf.test_linux_ccf("mt8365")

    @patch("linux_ccf.runcmd")
    def test_test_linux_ccf_fail_clk_summary(self, mock_runcmd):
        mock_runcmd.return_value = MagicMock(
            stdout="",
            stderr="error",
            returncode=1,
        )
        with self.assertRaises(SystemExit):
            ccf.test_linux_ccf("mt8390")

    @patch("linux_ccf.runcmd")
    @patch("linux_ccf.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("linux_ccf.PLAINBOX_SESSION_SHARE", "/share")
    def test_test_linux_ccf_mt8390(self, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(returncode=0),
            MagicMock(
                stdout="[-] Success, all clocks are mapped !",
                stderr="",
                returncode=0,
            ),
        ]
        ccf.test_linux_ccf("mt8390")
        mock_runcmd.assert_called_with(
            [
                "verify-mt8188-ccf.sh -t /tmp/linux-ccf/mt8188-clk.h"
                " -s /share/clk-summary.txt"
            ]
        )

    @patch("linux_ccf.runcmd")
    def test_test_linux_ccf_fail_verify(self, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1),
        ]
        with self.assertRaises(SystemExit):
            ccf.test_linux_ccf("mt8390")

    @patch("linux_ccf.runcmd")
    def test_test_linux_ccf_fail_verify_wrong_output(self, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(returncode=0),
            MagicMock(stdout="", returncode=0),
        ]
        with self.assertRaises(SystemExit):
            ccf.test_linux_ccf("mt8390")

    @patch("linux_ccf.runcmd")
    @patch("linux_ccf.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("linux_ccf.PLAINBOX_SESSION_SHARE", "/share")
    def test_test_linux_ccf_mt8395_or_mt8195(self, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(returncode=0),
            MagicMock(
                stdout="[-] Success, all clocks are mapped !",
                stderr="",
                returncode=0,
            ),
        ]
        cmd = [
            "verify-mt8195-ccf.sh -t /tmp/linux-ccf/mt8195-clk.h"
            " -s /share/clk-summary.txt"
        ]
        ccf.test_linux_ccf("mt8195")
        mock_runcmd.assert_called_with(cmd)

    @patch("linux_ccf.check_env_variables")
    @patch("linux_ccf.test_linux_ccf")
    def test_main(self, mock_test_linux_ccf, mock_check_env):
        with patch("sys.argv", ["soc", "mt8395"]):
            result = ccf.main()
        self.assertEqual(mock_test_linux_ccf.call_count, 1)
        self.assertEqual(result, None)

    @patch("linux_ccf.check_env_variables")
    @patch("linux_ccf.test_linux_ccf")
    def test_main_bad_args(self, mock_test_linux_ccf, mock_check_env):
        with patch("sys.argv", ["script_name", "bad_soc"]):
            with self.assertRaises(SystemExit):
                ccf.main()
        mock_test_linux_ccf.assert_not_called()

    @patch("linux_ccf.check_env_variables")
    @patch("linux_ccf.test_linux_ccf")
    def test_main_wrong_ccf(self, mock_test_linux_ccf, mock_check_env):
        mock_test_linux_ccf.side_effect = SystemExit(1)
        with patch("sys.argv", ["script_name", "mt8395"]):
            with self.assertRaises(SystemExit):
                ccf.main()
        mock_test_linux_ccf.assert_called_once_with("mt8395")
