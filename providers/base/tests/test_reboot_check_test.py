import shutil
from unittest.mock import mock_open, patch
import reboot_check_test as RCT
import unittest
import os
import typing as T


# manually override the return value based on arguments
def run_command_side_effect(args: T.List[str]) -> RCT.ShellResult:
    stdout = ""
    if args[0] == "iw":
        stdout = """
        addr some address
        Interface some interface
        ssid some ssid
        """
    elif args[0] == "checkbox-support-lsusb":
        stdout = """
        usb1
        usb2
        usb3
        """
    elif args[0] == "lspci":
        stdout = """
        pci1
        pci2
        pci3
        """
    else:
        raise Exception("Unexpected use of this mock")

    return RCT.ShellResult(0, stdout, "")


class RebootCheckTestTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.shared_resource = 1

    def test_parse_ok_unity_support_string(self):
        OK_UNITY_STRING = """
        OpenGL vendor string:   Intel
        OpenGL renderer string: Mesa Intel(R) UHD Graphics (ICL GT1)
        OpenGL version string:  4.6 (Compatibility Profile) Mesa 23.2.1-1ubuntu3.1~22.04.2

        Not software rendered:    [32;01myes[00m
        Not blacklisted:          [32;01myes[00m
        GLX fbconfig:             [32;01myes[00m
        GLX texture from pixmap:  [32;01myes[00m
        GL npot or rect textures: [32;01myes[00m
        GL vertex program:        [32;01myes[00m
        GL fragment program:      [32;01myes[00m
        GL vertex buffer object:  [32;01mno[00m
        GL framebuffer object:    [32;01myes[00m
        GL version is 1.4+:       [32;01myes[00m

        Unity 3D supported:       [32;01myes[00m
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
        GL version is 1.4+%       [32;01myes[00m
        """
        actual = RCT.parse_unity_support_output(BAD_UNITY_STRING)

        expected = {
            "OpenGL renderer string": "Mesa Intel(R) UHD Graphics (ICL GT1)",
        }

        self.assertDictEqual(expected, actual)

        ARBITRARY_STRING = "askjaskdnasdn"
        # should return empty dict if input string literally doesn't make sense
        self.assertEqual(RCT.parse_unity_support_output(ARBITRARY_STRING), {})

    @patch("reboot_check_test.run_command")
    def test_info_dump_only_happy_path(self, mock_run):
        print(os.getcwd())

        # manually override the return value based on arguments
        def run_command_side_effect(args: T.List[str]) -> RCT.ShellResult:
            stdout = ""
            if args[0] == "iw":
                stdout = """
                addr some address
                Interface some interface
                ssid some ssid
                """
            elif args[0] == "checkbox-support-lsusb":
                stdout = """
                usb1
                usb2
                usb3
                """
            elif args[0] == "lspci":
                stdout = """
                pci1
                pci2
                pci3
                """
            else:
                raise Exception("Unexpected use of this mock")

            return RCT.ShellResult(0, stdout, "")

        mock_run.side_effect = run_command_side_effect

        RCT.DeviceInfoCollector().dump(
            "{}/temporary_dump_directory".format(os.getcwd())
        )

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

    def test_main_function_logic(self):
        # this test only validates the main function logic(if it picks out the correct tests to run)
        do_nothing= lambda: None
        with patch(
            "reboot_check_test.DeviceInfoCollector.dump", new=do_nothing
        ):
            ...

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree("{}/temporary_dump_directory".format(os.getcwd()))
