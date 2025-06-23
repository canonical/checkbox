import shutil
from shlex import split as sh_split
from unittest.mock import MagicMock, mock_open, patch, DEFAULT
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


class DisplayConnectionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tester = RCT.HardwareRendererTester()
        RCT.RUNTIME_ROOT = ""
        RCT.SNAP = ""

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

    @patch("subprocess.run")
    def test_get_desktop_env_vars_no_desktop_session(
        self, mock_run: MagicMock
    ):
        def run_result(cmd_array: T.List[str], **_):
            if "pidof" in cmd_array:
                return sp.CompletedProcess(cmd_array, 1, "", "")

        mock_run.side_effect = run_result
        self.assertIsNone(
            RCT.HardwareRendererTester().get_desktop_environment_variables()
        )

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_get_desktop_env_vars_happy_path(
        self, mock_run: MagicMock, mock_check_output: MagicMock
    ):
        def run_result(cmd_array: T.List[str], **_):
            if cmd_array == ["pidof", "-s", "gnome-shell"]:
                return sp.CompletedProcess(cmd_array, 0, "12345", "")

        mock_run.side_effect = run_result
        mock_check_output.return_value = "\0".join(
            [
                "XDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu:/etc/xdg",
                "XDG_CURRENT_DESKTOP=ubuntu:GNOME",
                "XDG_SESSION_CLASS=user",
                "XDG_SESSION_DESKTOP=ubuntu-wayland",
                "XDG_SESSION_TYPE=wayland",
            ]
        )

        out = RCT.HardwareRendererTester().get_desktop_environment_variables()

        self.assertIsNotNone(out)

        self.assertDictEqual(
            out, # type: ignore
            {
                "XDG_CONFIG_DIRS": "/etc/xdg/xdg-ubuntu:/etc/xdg",
                "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
                "XDG_SESSION_CLASS": "user",
                "XDG_SESSION_DESKTOP": "ubuntu-wayland",
                "XDG_SESSION_TYPE": "wayland",
            },
        )

    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    @patch("subprocess.run")
    @patch("os.getenv")
    def test_is_hardware_renderer_available_fail(
        self,
        mock_getenv: MagicMock,
        mock_run: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,  # glmark2 returns 0 as long as it finishes
            """
=======================================================
    glmark2 2014.03+git20150611.fa71af2d
=======================================================
    OpenGL Information
    GL_VENDOR:     VMware, Inc.
    GL_RENDERER:   llvmpipe (LLVM 10.0.0, 256 bits)
    GL_VERSION:    3.1 Mesa 20.0.8
=======================================================
            """,
        )
        tester = RCT.HardwareRendererTester()
        self.assertFalse(tester.is_hardware_renderer_available())

        mock_run.reset_mock()
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,
            """
=======================================================
    glmark2 2023.01
=======================================================
    OpenGL Information
    GL_VENDOR:      Mesa
    GL_RENDERER:    softpipe
    GL_VERSION:     3.3 (Compatibility Profile) Mesa 24.2.8-1ubuntu1~24.04.1
    Surface Config: buf=32 r=8 g=8 b=8 a=8 depth=24 stencil=0 samples=0
    Surface Size:   800x600 windowed
=======================================================
            """,
        )
        self.assertFalse(tester.is_hardware_renderer_available())

        # somehow got no renderer string
        mock_run.reset_mock()
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,
            """
=======================================================
    glmark2 2023.01
=======================================================
    OpenGL Information
    GL_VENDOR:      Mesa
    Surface Config: buf=32 r=8 g=8 b=8 a=8 depth=24 stencil=0 samples=0
    Surface Size:   800x600 windowed
=======================================================
            """,
        )
        self.assertFalse(tester.is_hardware_renderer_available())

        # Real life example:
        # https://community.khronos.org/t/finding-opengl-es-2-0-mesa-
        # 18-3-4-on-rhel-7-for-mfix/108359
        mock_run.reset_mock()
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,
            """
=======================================================
    glmark2 2023.01
=======================================================
    OpenGL Information
    GL_VENDOR:      Mesa
    GL_RENDERER:    Software Rasterizer
    Surface Config: buf=32 r=8 g=8 b=8 a=8 depth=24 stencil=0 samples=0
    Surface Size:   800x600 windowed
=======================================================
            """,
        )
        self.assertFalse(tester.is_hardware_renderer_available())

    @patch("subprocess.run")
    @patch("os.getenv")
    def test_is_hardware_renderer_available_glmark2_timeout(
        self, mock_getenv: MagicMock, mock_run: MagicMock
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )

        def mock_run_side_effect(*args, **kwargs):
            if "glmark2" in args[0][0]:
                raise sp.TimeoutExpired(
                    ["glmark2"], 60, "glmark2 didn't return in 60 seconds"
                )
            else:
                return DEFAULT

        mock_run.side_effect = mock_run_side_effect
        tester = RCT.HardwareRendererTester()
        self.assertFalse(tester.is_hardware_renderer_available())

    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    @patch("subprocess.run")
    @patch("os.getenv")
    def test_is_hardware_renderer_available_happy_path(
        self,
        mock_getenv: MagicMock,
        mock_run: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,  # glmark2 returns 0 as long as it finishes
            """
=======================================================
    glmark2 2023.01
=======================================================
    OpenGL Information
    GL_VENDOR:      Intel
    GL_RENDERER:    Mesa Intel(R) Graphics (LNL)
    GL_VERSION:     4.6 (Compatibility Profile) Mesa 24.2.8-1ubuntu1~24.04.1
    Surface Config: buf=32 r=8 g=8 b=8 a=8 depth=24 stencil=0 samples=0
    Surface Size:   800x600 windowed
=======================================================
            """,
        )
        tester = RCT.HardwareRendererTester()
        self.assertTrue(tester.is_hardware_renderer_available())

    @patch("subprocess.run")
    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    def test_is_hardware_renderer_available_bad_session_type(
        self,
        mock_get_desktop_envs: MagicMock,
        mock_run: MagicMock,
    ):
        mock_get_desktop_envs.return_value = {
            "DISPLAY": "",
            "XDG_SESSION_TYPE": "tty",
        }  # found in `chvt` sessions
        tester = RCT.HardwareRendererTester()
        self.assertFalse(tester.is_hardware_renderer_available())

    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    @patch("subprocess.run")
    def test_is_hardware_renderer_available_chooses_correct_glmark(
        self,
        mock_run: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
        mock_run.side_effect = lambda *args, **kwargs: (
            sp.CompletedProcess(args, 0, "x86_64")
            if args[0][0] == "uname"
            else DEFAULT
        )
        tester = RCT.HardwareRendererTester()
        tester.is_hardware_renderer_available()
        # -1 is most recent call -> (args, kwargs, ...)
        # 0 takes the list of positional args
        # 0 again takes the 1st positional arg
        # last 0 is the 1st element in sp.run()'s command array
        self.assertEqual(mock_run.call_args_list[-1][0][0][0], "glmark2")

        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        }
        tester.is_hardware_renderer_available()
        # -1 is most recent call -> (args, kwargs, ...)
        # 0 takes the list of positional args
        # 0 again takes the 1st positional arg
        # last 0 is the 1st element in sp.run()'s command array
        self.assertEqual(
            mock_run.call_args_list[-1][0][0][0], "glmark2-wayland"
        )

    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    @patch("os.path.exists")
    @patch("os.path.islink")
    @patch("os.unlink")
    @patch("os.symlink")
    @patch("subprocess.run")
    @patch("os.getenv")
    def test_cleanup_glmark2_data_symlink(
        self,
        mock_getenv: MagicMock,
        mock_run: MagicMock,
        mock_symlink: MagicMock,
        mock_unlink: MagicMock,
        mock_islink: MagicMock,
        mock_path_exists: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        def custom_env(key: str, is_snap: bool) -> str:
            if key == "CHECKBOX_RUNTIME":
                return "/snap/runtime/path/" if is_snap else ""
            if key == "SNAP":
                return "/snap/checkbox/path/" if is_snap else ""

            raise Exception("unexpected use of this mock")

        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }

        mock_run.side_effect = lambda *args, **kwargs: (
            sp.CompletedProcess(args, 0, "x86_64")
            if args[0][0] == "uname"
            else DEFAULT
        )

        for is_snap in (True, False):

            mock_getenv.side_effect = lambda k: custom_env(k, is_snap)
            RCT.RUNTIME_ROOT = custom_env("CHECKBOX_RUNTIME", is_snap)
            RCT.SNAP = custom_env("SNAP", is_snap)
            mock_islink.return_value = is_snap
            # deb case, the file actually exists
            mock_path_exists.return_value = not is_snap
            # reapply the env variables
            tester = RCT.HardwareRendererTester()
            tester.is_hardware_renderer_available()

            if is_snap:
                mock_symlink.assert_called_once_with(
                    "{}/usr/share/glmark2".format(RCT.RUNTIME_ROOT),
                    "/usr/share/glmark2",
                    target_is_directory=True,
                )
                mock_unlink.assert_called_once_with("/usr/share/glmark2")
            else:
                mock_symlink.assert_not_called()
                mock_unlink.assert_not_called()

            mock_symlink.reset_mock()
            mock_unlink.reset_mock()

    def test_slow_boot_scenario(self):

        def fake_time(delta: int, ticks=2):
            # fake a time.time() delta using closure
            call_idx = [0]

            def wrapped():
                if call_idx[0] != ticks:
                    call_idx[0] += 1
                    return 0  # when time.time is initially called
                else:
                    return delta  # the "last" time when time.time is called

            return wrapped

        with patch("subprocess.run") as mock_run, patch(
            "time.sleep"
        ) as mock_sleep, patch("time.time") as mock_time, patch(
            "sys.argv",
            sh_split("reboot_check_test.py -g --graphical-target-timeout 2"),
        ):
            mock_run.side_effect = lambda *args, **kwargs: sp.CompletedProcess(
                [],
                1,
                "systemd says it's not ready",
                "graphical target not reached blah",
            )
            mock_sleep.side_effect = do_nothing
            mock_time.side_effect = fake_time(3)
            tester = RCT.HardwareRendererTester()

            self.assertFalse(tester.wait_for_graphical_target(2))

            mock_sleep.reset_mock()
            mock_time.side_effect = fake_time(3)
            tester = RCT.HardwareRendererTester()
            self.assertEqual(RCT.main(), 1)
            self.assertTrue(mock_time.called)
            self.assertTrue(mock_sleep.called)

            mock_time.side_effect = fake_time(3)
            mock_run.side_effect = sp.TimeoutExpired([], 1)
            tester = RCT.HardwareRendererTester()
            self.assertFalse(tester.wait_for_graphical_target(2))


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
        mock_run.return_value = sp.CompletedProcess([], 0, "", "")
        self.assertEqual(RCT.get_failed_services(), [])

    @patch("subprocess.run")
    def test_get_failed_services_with_failed_services(
        self, mock_run: MagicMock
    ):
        mock_run.return_value = sp.CompletedProcess(
            [],
            0,
            "snap.checkbox.agent.service loaded failed failed Service\
                  for snap applictaion checkbox.agent",
            "",
        )
        self.assertEqual(
            RCT.get_failed_services(), [mock_run.return_value.stdout]
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
            mock_compare.return_value = False

            rv = RCT.main()

            self.assertEqual(
                mock_run.call_count,
                len(RCT.DeviceInfoCollector.DEFAULT_DEVICES["required"]),
            )  # only lspci, lsusb, iw calls
            self.assertEqual(mock_compare.call_count, 1)
            self.assertEqual(rv, 1)

    @patch(
        "reboot_check_test."
        + "HardwareRendererTester.get_desktop_environment_variables"
    )
    @patch("subprocess.run")
    def test_main_function_full(
        self, mock_run: MagicMock, mock_get_desktop_envs
    ):
        mock_run.side_effect = do_nothing
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
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
            for _call in mock_run.call_args_list:
                # [0] takes the 1st from (args, kwargs, ) = call,
                # then take tha actual list from args
                # then take the 1st element, which is the command name
                actual.add(_call[0][0][0])

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


unittest.main()
