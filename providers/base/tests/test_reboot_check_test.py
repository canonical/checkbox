import shutil
from shlex import split as sh_split
from unittest.mock import MagicMock, mock_open, patch
import reboot_check_test as RCT
import unittest
import os
import typing as T
import subprocess as sp


def do_nothing(args: T.List[str], **kwargs):
    if "universal_newlines" in kwargs:
        return sp.CompletedProcess(args, 0, "", "")
    else:
        return sp.CompletedProcess(args, 0, "".encode(), "".encode())

class UnitySupportParserTests(unittest.TestCase):
    def setUp(self):
        self.tester = RCT.HardwareRendererTester()

    def test_parse_ok_unity_support_string(self):
        OK_UNITY_STRING = """\
        OpenGL vendor string:   Intel
        OpenGL renderer string: Mesa Intel(R) UHD Graphics (ICL GT1)
        OpenGL version string:  4.6 (Compatibility Profile) Mesa 23.2.1

        Not software rendered:    \x1B[033myes\x1B[0m
        Not blacklisted:          \x1B[033myes\x1B[0m
        GLX fbconfig:             \x1B[033myes\x1B[0m
        GLX texture from pixmap:  \x1B[033myes\x1B[0m
        GL npot or rect textures: \x1B[033myes\x1B[0m
        GL vertex program:        \x1B[033myes\x1B[0m
        GL fragment program:      \x1B[033myes\x1B[0m
        GL vertex buffer object:  \x1B[033mno\x1B[0m
        GL framebuffer object:    \x1B[033myes\x1B[0m
        GL version is 1.4+:       \x1B[033myes\x1B[0m

        Unity 3D supported:       \x1B[033myes\x1B[0m
        """

        expected = {
            "OpenGL vendor string": "Intel",
            "OpenGL renderer string": "Mesa Intel(R) UHD Graphics (ICL GT1)",
            "OpenGL version string": "4.6 (Compatibility Profile) Mesa 23.2.1",
            "Not software rendered": "yes",
            "Not blacklisted": "yes",
            "GLX fbconfig": "yes",
            "GLX texture from pixmap": "yes",
            "GL npot or rect textures": "yes",
            "GL vertex program": "yes",
            "GL fragment program": "yes",
            "GL vertex buffer object": "no",
            "GL framebuffer object": "yes",
            "GL version is 1.4+": "yes",
            "Unity 3D supported": "yes",
        }

        actual = self.tester.parse_unity_support_output(OK_UNITY_STRING)
        self.assertDictEqual(expected, actual)

    def test_parse_bad_unity_support_string(self):
        BAD_UNITY_STRING = """
        OpenGL vendor string   Intel
        OpenGL renderer string: Mesa Intel(R) UHD Graphics (ICL GT1)
        OpenGL version string  4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu
        GL version is 1.4+%       \x1B[033myes\x1B[0m
        """
        actual = self.tester.parse_unity_support_output(BAD_UNITY_STRING)

        expected = {
            "OpenGL renderer string": "Mesa Intel(R) UHD Graphics (ICL GT1)",
        }

        self.assertDictEqual(expected, actual)

        ARBITRARY_STRING = "askjaskdnasdn"
        # should return empty dict if input string literally doesn't make sense
        self.assertEqual(
            self.tester.parse_unity_support_output(ARBITRARY_STRING),
            {},
        )


class DisplayConnectionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tester = RCT.HardwareRendererTester()

    def test_display_check_happy_path(self):
        with patch(
            "os.listdir", return_value=["fakeCard0", "fakeCard1"]
        ), patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="connected",
        ):
            self.assertTrue(self.tester.has_display_connection())

    def test_display_check_no_display_path(self):
        with patch("os.listdir", return_value=["version"]):
            self.assertFalse(self.tester.has_display_connection())
        with patch(
            "os.listdir", return_value=["fakeCard0", "fakeCard1"]
        ), patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="not connected",
        ):
            self.assertFalse(self.tester.has_display_connection())

    @patch(
        "reboot_check_test.HardwareRendererTester.parse_unity_support_output"
    )
    @patch("subprocess.run")
    def test_is_hardware_renderer_available(
        self,
        mock_run: MagicMock,
        mock_parse: MagicMock,
    ):
        mock_run.side_effect = do_nothing
        mock_parse.return_value = {
            "Not software rendered": "yes",
        }
        tester = RCT.HardwareRendererTester()
        self.assertTrue(tester.is_hardware_renderer_available())

    @patch(
        "reboot_check_test.HardwareRendererTester.parse_unity_support_output"
    )
    @patch("subprocess.run")
    def test_is_hardware_renderer_available_fail(
        self,
        mock_run: MagicMock,
        mock_parse: MagicMock,
    ):
        mock_run.side_effect = lambda *args, **kwargs: sp.CompletedProcess(
            [], 1, "", ""
        )
        tester = RCT.HardwareRendererTester()
        self.assertFalse(tester.is_hardware_renderer_available())

        mock_run.reset_mock()
        mock_run.side_effect = do_nothing
        mock_parse.return_value = {
            "Not software rendered": "no",
        }
        tester = RCT.HardwareRendererTester()
        self.assertFalse(tester.is_hardware_renderer_available())


class InfoDumpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_output_dir = "{}/temp_output_dir".format(os.getcwd())
        cls.temp_comparison_dir = "{}/temp_comparison_dir".format(os.getcwd())

    def tearDown(self):
        shutil.rmtree(self.temp_output_dir, ignore_errors=True)
        shutil.rmtree(self.temp_comparison_dir, ignore_errors=True)

    def mock_run(self, args: T.List[str], **_) -> sp.CompletedProcess:
        stdout = ""
        if args[0] == "iw":
            stdout = """\
                addr some address
                Interface some interface
                ssid some ssid
                """
        elif args[0] == "checkbox-support-lsusb":
            stdout = """\
                usb1
                usb2
                usb3
                """
        elif args[0] == "lspci":
            stdout = """\
                pci1
                pci2
                pci3
                """
        else:
            raise Exception("Unexpected use of this mock")

        return sp.CompletedProcess(args, 0, stdout, "")

    @patch("subprocess.run")
    def test_info_dump_only_happy_path(self, mock_run: MagicMock):
        # wrap over run's return value
        mock_run.side_effect = self.mock_run
        RCT.DeviceInfoCollector().dump(self.temp_output_dir)

    @patch("subprocess.run")
    def test_info_dump_and_comparison_happy_path(self, mock_run: MagicMock):
        mock_run.side_effect = self.mock_run

        collector = RCT.DeviceInfoCollector()

        collector.dump(self.temp_comparison_dir)
        collector.dump(self.temp_output_dir)

        self.assertTrue(
            collector.compare_device_lists(
                self.temp_comparison_dir, self.temp_output_dir
            )
        )

        # required
        with open(
            "{}/{}_log".format(
                self.temp_comparison_dir,
                RCT.DeviceInfoCollector.Device.WIRELESS,
            ),
            "w",
        ) as f:
            f.write("extra text that shouldn't be there")

        self.assertFalse(
            collector.compare_device_lists(
                self.temp_comparison_dir, self.temp_output_dir
            )
        )

        collector.dump(self.temp_comparison_dir)

        # optional
        with open(
            "{}/{}_log".format(
                self.temp_comparison_dir,
                RCT.DeviceInfoCollector.Device.DRM,
            ),
            "w",
        ) as f:
            f.write("extra text that shouldn't be there")

        self.assertTrue(
            collector.compare_device_lists(
                self.temp_comparison_dir, self.temp_output_dir
            )
        )


class FailedServiceCheckerTests(unittest.TestCase):

    @patch("subprocess.run")
    def test_get_failed_services_happy_path(self, mock_run: MagicMock):
        mock_run.return_value = sp.CompletedProcess(
            [], 0, "",""
        )
        self.assertEqual(RCT.get_failed_services(), [])

    @patch("subprocess.run")
    def test_get_failed_services_with_failed_services(
        self, mock_run: MagicMock
    ):
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,
            "snap.checkbox.agent.service loaded failed failed Service\
                  for snap applictaion checkbox.agent".encode(),
            "",
        )
        self.assertEqual(
            RCT.get_failed_services(), [mock_run.return_value.stdout.decode()]
        )


class MainFunctionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp_output_dir = "{}/temp_output_dir".format(os.getcwd())
        cls.tmp_comparison_dir = "{}/temp_comparison_dir".format(os.getcwd())

    def tearDown(self):
        shutil.rmtree(self.tmp_output_dir, ignore_errors=True)
        shutil.rmtree(self.tmp_comparison_dir, ignore_errors=True)

    @patch("subprocess.run")
    def test_partial_main(self, mock_run: MagicMock):
        # this test only validates the main function logic
        # (if it picks out the correct tests to run)
        mock_run.side_effect = do_nothing

        with patch(
            "sys.argv",
            sh_split("reboot_check_test.py -d {}".format(self.tmp_output_dir)),
        ):
            RCT.main()
            self.assertEqual(
                mock_run.call_count,
                len(RCT.DeviceInfoCollector.DEFAULT_DEVICES["required"]),
            )

        mock_run.reset_mock()

        with patch(
            "sys.argv",
            sh_split(
                'reboot_check_test.py -d "{}" -c "{}"'.format(
                    self.tmp_output_dir, self.tmp_comparison_dir
                )
            ),
        ), patch(
            "reboot_check_test.DeviceInfoCollector.compare_device_lists"
        ) as mock_compare:
            RCT.main()

            self.assertEqual(
                mock_run.call_count,
                len(RCT.DeviceInfoCollector.DEFAULT_DEVICES["required"]),
            )  # only lspci, lsusb, iw calls
            self.assertEqual(mock_compare.call_count, 1)

    @patch("subprocess.run")
    def test_main_function_full(self, mock_run: MagicMock):
        mock_run.side_effect = do_nothing
        # Full suite
        with patch(
            "sys.argv",
            sh_split(
                'reboot_check_test.py -d "{}" -c "{}" -f -s -g'.format(
                    self.tmp_output_dir, self.tmp_comparison_dir
                )
            ),
        ), patch(
            "reboot_check_test.DeviceInfoCollector.compare_device_lists"
        ) as mock_compare, patch(
            "reboot_check_test.FwtsTester.is_fwts_supported"
        ) as mock_is_fwts_supported:
            mock_is_fwts_supported.return_value = True
            mock_compare.return_value = True

            RCT.main()

            self.assertTrue(mock_is_fwts_supported.called)

            expected_commands = {
                "systemctl",
                "sleep_test_log_check.py",
                "fwts",
            }

            actual = set()
            for call in mock_run.call_args_list:
                # [0] takes the 1st from (args, kwargs, ) = call,
                # then take tha actual list from args
                # then take the 1st element, which is the command name
                actual.add(call[0][0][0])

            # <= is an overloaded operator for sets
            # that checks the isSubset relation
            self.assertLessEqual(
                expected_commands, actual, "should be a subset"
            )

            with patch(
                "reboot_check_test.get_failed_services"
            ) as mock_get_failed_services:
                mock_get_failed_services.return_value = [
                    "failed service1",
                    "failed service2",
                ]
                self.assertEqual(RCT.main(), 1)

    def test_only_comparison_is_specified(self):
        with patch(
            "sys.argv",
            sh_split(
                'reboot_check_test.py -c "{}"'.format(self.tmp_output_dir)
            ),
        ), self.assertRaises(ValueError):
            RCT.main()
