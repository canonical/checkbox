import shutil
from shlex import split as sh_split
from unittest.mock import MagicMock, mock_open, patch
import reboot_check_test as RCT
import unittest
import os
import typing as T


def do_nothing_run_cmd(_: T.List[str]):
    return RCT.ShellResult(0, "", "")


class UnitySupportParserTests(unittest.TestCase):
    def test_parse_ok_unity_support_string(self):
        OK_UNITY_STRING = """\
        OpenGL vendor string:   Intel
        OpenGL renderer string: Mesa Intel(R) UHD Graphics (ICL GT1)
        OpenGL version string:  4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu3.1~22.04.2

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
            "OpenGL version string": "4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu3.1~22.04.2",
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

        actual = RCT.parse_unity_support_output(OK_UNITY_STRING)
        self.assertDictEqual(expected, actual)

    def test_parse_bad_unity_support_string(self):
        BAD_UNITY_STRING = """
        OpenGL vendor string   Intel
        OpenGL renderer string: Mesa Intel(R) UHD Graphics (ICL GT1)
        OpenGL version string  4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu3.1~22.04.2
        GL version is 1.4+%       \x1B[033myes\x1B[0m
        """
        actual = RCT.parse_unity_support_output(BAD_UNITY_STRING)

        expected = {
            "OpenGL renderer string": "Mesa Intel(R) UHD Graphics (ICL GT1)",
        }

        self.assertDictEqual(expected, actual)

        ARBITRARY_STRING = "askjaskdnasdn"
        # should return empty dict if input string literally doesn't make sense
        self.assertEqual(RCT.parse_unity_support_output(ARBITRARY_STRING), {})


class DisplayConnectionTests(unittest.TestCase):
    def test_display_check_happy_path(self):
        with patch("os.listdir", return_value=["card0", "card1"]), patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="connected",
        ):
            self.assertTrue(RCT.has_display_connection())

    def test_display_check_no_display_path(self):
        with patch("os.listdir", return_value=["version"]):
            self.assertFalse(RCT.has_display_connection())
        with patch("os.listdir", return_value=["card0", "card1"]), patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="not connected",
        ):
            self.assertFalse(RCT.has_display_connection())

    def test_is_hardware_renderer_available(self):
        self.assertTrue(RCT.is_hardware_renderer_available())

    @patch("reboot_check_test.run_command")
    def test_get_display_id(self, mock_run: MagicMock):
        with patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual(RCT.get_display_id(), ":0")

        def create_side_effect(
            display_server_name: 'T.Literal["wayland", "x11", "tty"]',
        ):
            def side_effect(args: T.List[str]):
                stdout = ""
                if args[0] == "loginctl":
                    stdout = "Type={}".format(display_server_name)
                if args[0] == "pgrep":
                    stdout = "75632 /usr/bin/Xwayland :0 -rootless -noreset -accessx -core -auth /run/user/1000/.mutter-Xwaylandauth.FFE5P2"
                if args[0] == "w":
                    stdout = "ubuntu :0 :0 13:43 13:55m  0.01s  0.00s /usr/libexec/gdm-wayland-session en"

                return RCT.ShellResult(0, stdout, "")

            return side_effect

        with patch.dict(os.environ, {"DISPLAY": ""}):
            mock_run.side_effect = create_side_effect("wayland")
            self.assertEqual(RCT.get_display_id(), ":0")

            mock_run.reset_mock()
            mock_run.side_effect = create_side_effect("x11")
            self.assertEqual(RCT.get_display_id(), ":0")


class InfoDumpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_output_dir = "{}/temp_output_dir".format(os.getcwd())
        cls.temp_comparison_dir = "{}/temp_comparison_dir".format(os.getcwd())

    def tearDown(self):
        shutil.rmtree(self.temp_output_dir, ignore_errors=True)
        shutil.rmtree(self.temp_comparison_dir, ignore_errors=True)

    def mock_run_command(self, args: T.List[str]) -> RCT.ShellResult:
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

        return RCT.ShellResult(0, stdout, "")

    @patch("reboot_check_test.run_command")
    def test_info_dump_only_happy_path(self, mock_run: MagicMock):
        # wrap over run_command's return value
        mock_run.side_effect = self.mock_run_command
        RCT.DeviceInfoCollector().dump(self.temp_output_dir)

    @patch("reboot_check_test.run_command")
    def test_info_dump_and_comparison_happy_path(self, mock_run: MagicMock):
        mock_run.side_effect = self.mock_run_command

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
                RCT.DeviceInfoCollector.Device.WIRELESS.value,
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
                self.temp_comparison_dir, RCT.DeviceInfoCollector.Device.DRM.value
            ),
            "w",
        ) as f:
            f.write("extra text that shouldn't be there")

        self.assertTrue(
            collector.compare_device_lists(
                self.temp_comparison_dir, self.temp_output_dir
            )
        )


class MainFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = "{}/temporary_dump_directory".format(os.getcwd())

    @patch("reboot_check_test.run_command")
    def test_partial_main(self, mock_run: MagicMock):
        # this test only validates the main function logic(if it picks out the correct tests to run)
        mock_run.side_effect = do_nothing_run_cmd

        with patch(
            "sys.argv",
            sh_split("reboot_check_test.py -d {}".format(self.temp_directory)),
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
                    self.temp_directory, "some dir"
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

    @patch("reboot_check_test.get_display_id")
    @patch("reboot_check_test.run_command")
    def test_main_function_full(
        self, mock_run: MagicMock, mock_get_display_id: MagicMock
    ):
        mock_run.side_effect = do_nothing_run_cmd
        mock_get_display_id.return_value = ":0"
        # Full suite
        with patch(
            "sys.argv",
            sh_split(
                'reboot_check_test.py -d "{}" -c "{}" -f -s -g'.format(
                    self.temp_directory, "some dir"
                )
            ),
        ), patch(
            "reboot_check_test.DeviceInfoCollector.compare_device_lists"
        ) as mock_compare, patch(
            "reboot_check_test.is_fwts_supported"
        ) as mock_fwts_support_check:
            mock_fwts_support_check.return_value = True
            RCT.main()

            self.assertTrue(mock_compare.called)
            self.assertTrue(mock_fwts_support_check.called)

            expected_commands = {
                "systemctl",
                "sleep_test_log_check.py",
            }

            actual = set()
            for call in mock_run.call_args_list:
                # [0] takes the 1st from (args, kwargs, ) = call,
                # then take tha actual list from args
                # then take the 1st element, which is the command name
                actual.add(call[0][0][0])

            # <= is an overloaded operator for sets that checks the isSubset relation
            self.assertLessEqual(expected_commands, actual)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_directory)
