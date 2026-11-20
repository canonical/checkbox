#!/usr/bin/env python3

import io
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import eglinfo_test

GBM_MALI_OUTPUT = (
    "GBM platform:\n"
    "EGL vendor string: ARM\n"
    "OpenGL ES profile vendor: ARM\n"
    "OpenGL ES profile renderer: Mali-G57\n"
)

SURFACELESS_LLVMPIPE_OUTPUT = (
    "Surfaceless platform:\n"
    "libEGL warning: egl: failed to create dri2 screen\n"
    "EGL vendor string: Mesa Project\n"
    "OpenGL core profile renderer: llvmpipe (LLVM 20.1.2, 128 bits)\n"
)


class TestResource(unittest.TestCase):
    @patch.dict(
        os.environ,
        {eglinfo_test.EGLINFO_IGNORED_PLATFORM: " X11, surfaceless, ,GBM "},
    )
    def test_parse_ignored_set_normalizes_platform_names(self):
        self.assertEqual(
            eglinfo_test.parse_ignored_set(),
            {"x11", "surfaceless", "gbm"},
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_parse_ignored_set_is_empty_when_unset(self):
        self.assertEqual(eglinfo_test.parse_ignored_set(), set())

    @patch("eglinfo_test.eglinfo_supports_platform_option", return_value=True)
    @patch.dict(
        os.environ, {eglinfo_test.EGLINFO_IGNORED_PLATFORM: "wayland,x11"}
    )
    def test_cmd_resource_prints_all_platforms_and_ignore_flags(self, *_):
        output = io.StringIO()

        with redirect_stdout(output):
            result = eglinfo_test.cmd_resource()

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            "platform_name: gbm\n"
            "ignore: false\n\n"
            "platform_name: wayland\n"
            "ignore: true\n\n"
            "platform_name: x11\n"
            "ignore: true\n\n"
            "platform_name: surfaceless\n"
            "ignore: false\n\n",
        )

    @patch("eglinfo_test.eglinfo_supports_platform_option", return_value=False)
    def test_cmd_resource_eglinfo_without_p_emits_all(self, *_):
        output = io.StringIO()

        with redirect_stdout(output):
            eglinfo_test.cmd_resource()

        self.assertEqual(
            output.getvalue(), "platform_name: all\nignore: false\n\n"
        )

    @patch("eglinfo_test.subprocess.run")
    def test_eglinfo_supports_platform_option(self, mock_run):
        mock_run.return_value.stdout = "Usage: eglinfo [-h] [-p <platform>]"
        self.assertTrue(eglinfo_test.eglinfo_supports_platform_option())
        mock_run.return_value.stdout = "Usage: eglinfo [-h] [-B] [-s]"
        self.assertFalse(eglinfo_test.eglinfo_supports_platform_option())
        mock_run.side_effect = FileNotFoundError()
        self.assertTrue(eglinfo_test.eglinfo_supports_platform_option())

    @patch("eglinfo_test.eglinfo_supports_platform_option", return_value=True)
    def test_cmd_resource_unknown_version_emits_platforms(self, *_):
        output = io.StringIO()

        with redirect_stdout(output):
            eglinfo_test.cmd_resource()

        self.assertIn("platform_name: gbm", output.getvalue())

    @patch("eglinfo_test.subprocess.check_output")
    def test_get_mesa_utils_version(self, mock_check_output):
        mock_check_output.return_value = "8.4.0-1ubuntu1"
        self.assertEqual(
            eglinfo_test.get_mesa_utils_version(), "8.4.0-1ubuntu1"
        )
        mock_check_output.side_effect = FileNotFoundError()
        self.assertEqual(eglinfo_test.get_mesa_utils_version(), "unknown")


class TestEglinfoEnviron(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"LD_LIBRARY_PATH": "/snap/checkbox24/current/usr/lib", "A": "1"},
        clear=True,
    )
    def test_drops_inherited_ld_library_path(self):
        self.assertEqual(eglinfo_test.eglinfo_environ(), {"A": "1"})

    @patch.dict(
        os.environ,
        {
            "LD_LIBRARY_PATH": "/snap/checkbox24/current/usr/lib",
            "EGLINFO_LD_LIBRARY_PATH": "/opt/gpu/lib",
        },
        clear=True,
    )
    def test_uses_eglinfo_ld_library_path(self):
        env = eglinfo_test.eglinfo_environ()

        self.assertEqual(env["LD_LIBRARY_PATH"], "/opt/gpu/lib")


@patch.dict(os.environ, {}, clear=True)
@patch("eglinfo_test.subprocess.check_output")
class TestRunEglinfo(unittest.TestCase):
    def test_default_command(self, mock_check_output):
        mock_check_output.return_value = "out"

        self.assertEqual(eglinfo_test.run_eglinfo("gbm"), "out")
        self.assertEqual(
            mock_check_output.call_args[0][0],
            ["eglinfo", "-B", "-p", "gbm"],
        )
        self.assertNotIn(
            "LD_LIBRARY_PATH", mock_check_output.call_args[1]["env"]
        )

    def test_all_platform_runs_plain_eglinfo(self, mock_check_output):
        eglinfo_test.run_eglinfo("all")

        self.assertEqual(mock_check_output.call_args[0][0], ["eglinfo"])

    @patch("eglinfo_test.get_mesa_utils_version", return_value="8.4.0")
    @patch("eglinfo_test.is_snap_eglinfo", return_value=False)
    def test_all_logs_host_and_mesa_utils(self, _, __, mock_check_output):
        with self.assertLogs(eglinfo_test.logger, "INFO") as logs:
            eglinfo_test.run_eglinfo("all")

        text = "\n".join(logs.output)
        self.assertIn("eglinfo source: host", text)
        self.assertIn("mesa-utils version: 8.4.0", text)

    @patch("eglinfo_test.get_mesa_utils_version")
    @patch("eglinfo_test.is_snap_eglinfo", return_value=True)
    def test_all_logs_snap_without_mesa_utils(
        self, _, mock_version, mock_check_output
    ):
        with self.assertLogs(eglinfo_test.logger, "INFO") as logs:
            eglinfo_test.run_eglinfo("all")

        self.assertIn("eglinfo source: snap", "\n".join(logs.output))
        mock_version.assert_not_called()

    def test_tolerates_undecodable_output(self, mock_check_output):
        eglinfo_test.run_eglinfo("gbm")

        self.assertEqual(mock_check_output.call_args[1]["errors"], "replace")

    def test_custom_command_from_environ(self, mock_check_output):
        os.environ["CUSTOM_EGLINFO_COMMAND_PATH"] = "snap.eglinfo"

        eglinfo_test.run_eglinfo("wayland")

        self.assertEqual(
            mock_check_output.call_args[0][0],
            ["snap.eglinfo", "-B", "-p", "wayland"],
        )

    def test_command_not_found(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("eglinfo")

        with self.assertRaises(SystemExit):
            eglinfo_test.run_eglinfo("gbm")

    def test_egl_initialize_failed(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, ["eglinfo"], output="eglinfo: eglInitialize failed\n"
        )

        with self.assertRaises(SystemExit):
            eglinfo_test.run_eglinfo("wayland")


@patch("eglinfo_test.run_eglinfo")
class TestCmdTest(unittest.TestCase):
    def test_fails_without_renderer(self, mock_run):
        mock_run.return_value = ""

        with self.assertRaises(SystemExit):
            eglinfo_test.cmd_test("x11")

    def test_fails_on_software_renderer(self, mock_run):
        mock_run.return_value = SURFACELESS_LLVMPIPE_OUTPUT

        with self.assertRaises(SystemExit):
            eglinfo_test.cmd_test("surfaceless")

    def test_passes_for_hardware_renderer(self, mock_run):
        mock_run.return_value = GBM_MALI_OUTPUT

        self.assertEqual(eglinfo_test.cmd_test("gbm"), 0)
        mock_run.assert_called_once_with("gbm")

    def test_all_passes_without_renderer_line(self, mock_run):
        mock_run.return_value = "GBM platform:\nEGL vendor string: ARM\n"

        self.assertEqual(eglinfo_test.cmd_test("all"), 0)

    def test_all_fails_on_software_renderer(self, mock_run):
        mock_run.return_value = SURFACELESS_LLVMPIPE_OUTPUT

        with self.assertRaises(SystemExit):
            eglinfo_test.cmd_test("all")

    def test_all_fails_on_egl_initialize_failed(self, mock_run):
        mock_run.return_value = "Wayland platform:\neglInitialize failed\n"

        with self.assertRaises(SystemExit):
            eglinfo_test.cmd_test("all")


class TestMain(unittest.TestCase):
    @patch("eglinfo_test.cmd_resource", return_value=0)
    @patch("sys.argv", ["eglinfo_test.py", "resource", "--debug"])
    def test_main_routes_resource(self, mock_cmd_resource):
        self.assertEqual(eglinfo_test.main(), 0)
        mock_cmd_resource.assert_called_once_with()

    @patch("eglinfo_test.cmd_test", return_value=0)
    @patch("sys.argv", ["eglinfo_test.py", "test", "-p", "gbm"])
    def test_main_routes_test(self, mock_cmd_test):
        self.assertEqual(eglinfo_test.main(), 0)
        mock_cmd_test.assert_called_once_with("gbm")


if __name__ == "__main__":
    unittest.main()
