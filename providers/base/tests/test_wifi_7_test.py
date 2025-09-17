import pathlib
import unittest as ut
import wifi_7_test as w7
from unittest.mock import MagicMock, patch
from checkbox_support.helpers.retry import mock_retry

TEST_DATA_DIR = pathlib.Path(__file__).parent / "test_data"
MOCK_AP_NAME = "wifi7-ap"


class TestWifi7Tests(ut.TestCase):

    @mock_retry()
    @patch(
        "sys.argv", ["wifi_7_test.py", "-m", MOCK_AP_NAME, "-p", "password123"]
    )
    @patch("subprocess.run")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_happy_path(
        self,
        mock_check_output: MagicMock,
        mock_check_call: MagicMock,
        mock_run: MagicMock,
    ):
        def fake_check_output(args: "list[str]", *other_args, **kwargs):
            iface = "wlp0s20f3"
            if args == [
                "nmcli",
                "-get-values",
                "GENERAL.DEVICE,GENERAL.TYPE",
                "device",
                "show",
            ]:
                return "\n".join([iface, "wifi", "", "lo", "loopback"])
            if args == ["iw", "dev", iface, "info"]:
                with (TEST_DATA_DIR / "iw_dev_info_succ.txt").open() as f:
                    return f.read()
            if args == ["iw", "dev", iface, "link"]:
                with (TEST_DATA_DIR / "iw_dev_link_succ.txt").open() as f:
                    return f.read()
            if args == [
                "nmcli",
                "-get-values",
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
        w7.main()

    def test_parser_happy_path(self):
        with (TEST_DATA_DIR / "iw_dev_link_succ.txt").open() as f:
            # tx bitrate: 4803.8 MBit/s 320MHz EHT-MCS 11 EHT-NSS 2 EHT-GI 0
            expected = w7.ConnectionInfo(
                mcs=11, conn_type="EHT", direction="tx", bandwidth=320
            )
            actual, _ = w7.ConnectionInfo.parse(f.read())
            for prop in dir(expected):
                if prop.startswith("__"):
                    # don't compare dunder methods/props
                    continue
                self.assertEqual(
                    getattr(expected, prop), getattr(actual, prop)
                )

    @patch("sys.argv", ["wifi_7_test.py", ""])
    def test_not_wifi_7(
        self,
    ):
        pass


if __name__ == "__main__":
    ut.main()
