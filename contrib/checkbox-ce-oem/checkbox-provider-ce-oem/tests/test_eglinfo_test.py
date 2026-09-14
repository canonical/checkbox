#!/usr/bin/env python3

import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import eglinfo_test


class TestEglinfoTest(unittest.TestCase):
	@patch(
		"eglinfo_test.resolve_configured_commands",
		return_value={"eglinfo": "configured-eglinfo"},
	)
	def test_resolve_eglinfo_command_delegates_to_general_utils(
		self, mock_resolve
	):
		result = eglinfo_test._resolve_eglinfo_command(enable_logger=True)

		self.assertEqual(result, "configured-eglinfo")
		mock_resolve.assert_called_once_with(
			default_commands=[eglinfo_test.EXECUTABLE_CMD],
			enable_logger=True,
		)

	@patch("subprocess.run")
	def test_run_eglinfo_command_combines_output(self, mock_run):
		mock_run.return_value = subprocess.CompletedProcess(
			args="eglinfo -B -p gbm",
			returncode=2,
			stdout="eglInitialize failed\n",
		)

		result = eglinfo_test._run_eglinfo_command("eglinfo -B -p gbm")

		self.assertEqual(result, (2, "eglInitialize failed\n"))
		mock_run.assert_called_once_with(
			"eglinfo -B -p gbm",
			shell=True,
			check=False,
			text=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
		)

	@patch.dict(
		os.environ,
		{eglinfo_test.EGLINFO_IGNORED_PLATFORM: " X11, surfaceless, ,GBM "},
		clear=False,
	)
	def test_parse_ignored_set_normalizes_platform_names(self):
		self.assertEqual(
			eglinfo_test.parse_ignored_set(),
			{"x11", "surfaceless", "gbm"},
		)

	@patch.dict(os.environ, {}, clear=True)
	def test_parse_ignored_set_is_empty_when_unset(self):
		self.assertEqual(eglinfo_test.parse_ignored_set(), set())

	@patch.dict(
		os.environ,
		{eglinfo_test.EGLINFO_IGNORED_PLATFORM: "wayland,x11"},
		clear=False,
	)
	def test_cmd_resource_prints_all_platforms_and_ignore_flags(self):
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

	@patch("eglinfo_test._resolve_eglinfo_command", return_value="")
	def test_cmd_test_fails_when_eglinfo_is_missing(self, _mock_resolve):
		self.assertEqual(eglinfo_test.cmd_test("gbm"), 1)

	@patch("eglinfo_test._resolve_eglinfo_command", return_value="eglinfo")
	@patch("eglinfo_test._run_eglinfo_command", return_value=(0, ""))
	def test_cmd_test_fails_without_output(self, mock_run, _mock_resolve):
		self.assertEqual(eglinfo_test.cmd_test("wayland"), 1)
		mock_run.assert_called_once_with(
			"eglinfo -B -p wayland", enable_logger=True
		)

	@patch("eglinfo_test._resolve_eglinfo_command", return_value="eglinfo")
	@patch(
		"eglinfo_test._run_eglinfo_command",
		return_value=(1, "eglInitialize failed for platform\n"),
	)
	def test_cmd_test_fails_on_egl_initialize_error(
		self, _mock_run, _mock_resolve
	):
		self.assertEqual(eglinfo_test.cmd_test("x11"), 1)

	@patch("eglinfo_test._resolve_eglinfo_command", return_value="eglinfo")
	@patch(
		"eglinfo_test._run_eglinfo_command",
		return_value=(0, "OpenGL renderer: Mesa llvmpipe (LLVM 18.0.0)\n"),
	)
	def test_cmd_test_fails_on_software_renderer(
		self, _mock_run, _mock_resolve
	):
		self.assertEqual(eglinfo_test.cmd_test("surfaceless"), 1)

	@patch("eglinfo_test._resolve_eglinfo_command", return_value="eglinfo")
	@patch(
		"eglinfo_test._run_eglinfo_command",
		return_value=(0, "OpenGL renderer: Mali-G610\n"),
	)
	def test_cmd_test_passes_for_hardware_renderer(
		self, mock_run, _mock_resolve
	):
		self.assertEqual(eglinfo_test.cmd_test("gbm"), 0)
		mock_run.assert_called_once_with(
			"eglinfo -B -p gbm", enable_logger=True
		)

	def test_build_parser_parses_resource_and_test_actions(self):
		parser = eglinfo_test.build_parser()

		resource_args = parser.parse_args(["resource", "--debug"])
		test_args = parser.parse_args(["test", "-p", "gbm"])

		self.assertEqual(resource_args.action, "resource")
		self.assertTrue(resource_args.debug)
		self.assertEqual(test_args.action, "test")
		self.assertEqual(test_args.platform, "gbm")


if __name__ == "__main__":
	unittest.main()
