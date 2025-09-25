import os
import subprocess
import unittest as ut
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock, patch

import wifi_7_test as w7
from checkbox_support.helpers.retry import mock_retry

TEST_DATA_DIR = Path(__file__).parent / "test_data"
MOCK_AP_NAME = "wifi7-ap"


class TestStrUtils(ut.TestCase):
    def test_remove_prefix_and_suffix(self):
        self.assertEqual(w7.remove_prefix("pref123", "pref"), "123")
        self.assertEqual(w7.remove_prefix("pref123", "pref123"), "")
        self.assertEqual(w7.remove_prefix("pre", "pref123"), "pre")

        self.assertEqual(w7.remove_suffix("pref123", "123"), "pref")
        self.assertEqual(w7.remove_suffix("pref123", "pref123"), "")
        self.assertEqual(w7.remove_suffix("pre", "pref123"), "pre")


@patch.dict(os.environ, {"PLAINBOX_SESSION_SHARE": "session-share"}, clear=True)
class TestWifi7Tests(ut.TestCase):

    @mock_retry()
    @patch("builtins.open")
    @patch("time.sleep")
    @patch("subprocess.run")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_happy_path(
        self,
        mock_check_output: MagicMock,
        mock_check_call: MagicMock,
        mock_run: MagicMock,
        mock_sleep,
        mock_open,
    ):
        def fake_check_output(args: "list[str]", *other_args, **kwargs):
            iface = "wlp0s20f3"
            if args[0:3] == ["nmcli", "connection", "delete"]:
                return "Deleted {}".format(args[3])
            if args[0:5] == [
                "nmcli",
                "--get-values",
                "GENERAL.DEVICE,GENERAL.TYPE",
                "device",
                "show",
            ]:
                return "\n".join([iface, "wifi", "", "lo", "loopback"])
            if args[0:4] == ["iw", "dev", iface, "info"]:
                with (TEST_DATA_DIR / "iw_dev_info_succ.txt").open() as f:
                    return f.read()
            if args[0:4] == ["iw", "dev", iface, "link"]:
                with (TEST_DATA_DIR / "iw_dev_link_succ.txt").open() as f:
                    return f.read()
            if args[0:8] == [
                "nmcli",
                "--get-values",
                "SSID",
                "device",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ]:
                return "\n".join(
                    [
                        "some-other-random-wifi",
                        "wifi6-ap",
                        "",  # nmcli output can have random new lines
                        "",
                        "some-random-wifi",
                        MOCK_AP_NAME,
                    ]
                )

        mock_check_output.side_effect = fake_check_output
        mock_run.return_value = subprocess.CompletedProcess([], 10, "", "")
        with patch(
            "sys.argv",
            ["wifi_7_test.py", "-m", MOCK_AP_NAME, "-p", "password123"],
        ):
            w7.main()

        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with patch(
            "sys.argv",
            [
                "wifi_7_test.py",
                "-m",
                MOCK_AP_NAME,
                "-p",
                "password123",
                "-i",
                "wlp0s20f3",
            ],
        ), patch("wifi_7_test.get_wifi_interface") as mock_get_iface:
            w7.main()
            mock_get_iface.assert_not_called()

    def test_parser_happy_path(self):
        with (TEST_DATA_DIR / "iw_dev_link_succ.txt").open() as f:
            # tx bitrate: 4803.8 MBit/s 320MHz EHT-MCS 11 EHT-NSS 2 EHT-GI 0
            expected = w7.ConnectionInfo(
                mcs=12, conn_type="EHT", direction="tx", bandwidth=320
            )
            actual, _ = w7.ConnectionInfo.parse(f.read())
            for prop in dir(expected):
                if prop.startswith("__"):
                    # don't compare dunder methods/props
                    continue
                self.assertEqual(
                    getattr(expected, prop), getattr(actual, prop)
                )

    @mock_retry()
    @patch("builtins.open")
    @patch("time.sleep")
    @patch(
        "sys.argv", ["wifi_7_test.py", "-m", MOCK_AP_NAME, "-p", "password123"]
    )
    @patch("subprocess.run")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_not_wifi_7(
        self,
        mock_check_output: MagicMock,
        mock_check_call: MagicMock,
        mock_run: MagicMock,
        mock_sleep,
        mock_open,
    ):
        def fake_check_output(args: "list[str]", *other_args, **kwargs):
            iface = "wlp0s20f3"
            if args[0:5] == [
                "nmcli",
                "--get-values",
                "GENERAL.DEVICE,GENERAL.TYPE",
                "device",
                "show",
            ]:
                return "\n".join([iface, "wifi", "", "lo", "loopback"])
            if args[0:4] == ["iw", "dev", iface, "info"]:
                with (
                    TEST_DATA_DIR / "iw_dev_info_not_wifi_7.txt"
                ).open() as f:
                    return f.read()
            if args[0:4] == ["iw", "dev", iface, "link"]:
                with (
                    TEST_DATA_DIR / "iw_dev_link_not_wifi_7.txt"
                ).open() as f:
                    return f.read()
            if args[0:8] == [
                "nmcli",
                "--get-values",
                "SSID",
                "device",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ]:
                return "\n".join(
                    [
                        "some-other-random-wifi",
                        "wifi7-ap",
                        "",  # nmcli output can have random new lines
                        "",
                        "some-random-wifi",
                        MOCK_AP_NAME,
                    ]
                )

        mock_check_output.side_effect = fake_check_output
        self.assertRaises(SystemExit, w7.main)

    @mock_retry()
    @patch("builtins.open")
    @patch("time.sleep")
    @patch(
        "sys.argv", ["wifi_7_test.py", "-m", MOCK_AP_NAME, "-p", "password123"]
    )
    @patch("subprocess.run")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_connection_assertions(
        self,
        mock_check_output: MagicMock,
        mock_check_call: MagicMock,
        mock_run: MagicMock,
        mock_sleep,
        mock_open,
    ):
        # device doesn't have wifi
        mock_check_output.return_value = "\n".join(
            ["lo", "loopback", "", "enp133s0", "ethernet"]
        )
        with self.assertRaises(SystemExit):
            w7.main()

        mock_check_output.reset_mock()

        def fake_check_output(args: "list[str]", *other_args, **kwargs):
            iface = "wlp0s20f3"
            if args[0:5] == [
                "nmcli",
                "--get-values",
                "GENERAL.DEVICE,GENERAL.TYPE",
                "device",
                "show",
            ]:
                return "\n".join([iface, "wifi", "", "lo", "loopback"])

            if args[0:8] == [
                "nmcli",
                "--get-values",
                "SSID",
                "device",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ]:
                return "\n".join(
                    [
                        "some-other-random-wifi",
                        "wifi6-ap",
                        "",
                        "",
                        "some-random-wifi",
                    ]
                )

        mock_check_output.side_effect = fake_check_output
        # didn't find the given AP, exit
        with self.assertRaises(SystemExit):
            w7.main()

    @mock_retry()
    @patch("builtins.open")
    @patch("time.sleep")
    @patch("sys.argv", ["wifi_7_test.py", "-m", MOCK_AP_NAME])
    @patch("subprocess.run")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_dont_specify_password_if_not_given(
        self,
        mock_check_output: MagicMock,
        mock_check_call: MagicMock,
        mock_run: MagicMock,
        mock_sleep,
        mock_open,
    ):

        mock_check_output.return_value = "\n".join(
            [
                "some-other-random-wifi",
                "wifi6-ap",
                "",
                "",
                "some-random-wifi",
                "",
                MOCK_AP_NAME,
            ]
        )
        with suppress(SystemExit):
            w7.connect(MOCK_AP_NAME, None)

        self.assertListEqual(
            mock_check_call.call_args[0][0],
            ["nmcli", "device", "wifi", "connect", MOCK_AP_NAME],
        )


if __name__ == "__main__":
    ut.main()
