#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
"""Tests for `check_notebook.py`"""

import argparse
import contextlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import check_notebook


class TestCreateParser(unittest.TestCase):
    check_names = ["check1", "check_2"]

    def test_has_help(self):
        parser = check_notebook.create_parser(self.check_names)
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)

    def test_normal_success(self):
        parser = check_notebook.create_parser(self.check_names)
        parsed = parser.parse_args(["notebook_1", "check1"])
        with self.subTest("notebook name"):
            self.assertEqual(parsed.notebook_name, "notebook_1")
        with self.subTest("check name"):
            self.assertEqual(parsed.check_name, "check1")

    def test_accepts_all_check_names(self):
        parser = check_notebook.create_parser(self.check_names)
        for check in self.check_names:
            with self.subTest(check):
                parsed = parser.parse_args(["notebook", check])
            self.assertEqual(parsed.check_name, check)

    def test_exits_with_code_2_on_unknown_check_name(self):
        parser = check_notebook.create_parser(self.check_names)
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(["notebook", "not a check"])
        self.assertEqual(raised.exception.code, 2)

    def test_exits_with_code_2_on_missing_notebook_name(self):
        parser = check_notebook.create_parser(self.check_names)
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args([self.check_names[0]])
        self.assertEqual(raised.exception.code, 2)

    def test_exits_with_code_2_on_missing_check_name(self):
        parser = check_notebook.create_parser(self.check_names)
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(["notebook"])
        self.assertEqual(raised.exception.code, 2)

    def test_exits_with_code_2_on_too_many_args(self):
        parser = check_notebook.create_parser(self.check_names)
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(
                [
                    "notebook",
                    self.check_names[0],
                    self.check_names[1],
                ]
            )
        self.assertEqual(raised.exception.code, 2)


class TestAvailableChecks(unittest.TestCase):
    def test_picks_python_scripts_from_env_var(self):
        check_names = ["check1", "check_2"]
        script_names = [f"{name}.py" for name in check_names]

        with tempfile.TemporaryDirectory() as d:
            os.environ["PLAINBOX_PROVIDER_DATA"] = d
            for script in script_names:
                (Path(d) / script).touch()
            actual = check_notebook.get_available_checks()

        with self.subTest("picks check names"):
            self.assertListEqual(sorted(actual.keys()), check_names)
        for check, script in zip(check_names, script_names):
            with self.subTest(f"script path for {check}"):
                actual_script_path = actual[check]
                self.assertEqual(actual_script_path, Path(d) / script)

    def test_raises_error_when_data_dir_has_no_scripts(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["PLAINBOX_PROVIDER_DATA"] = d
            (Path(d) / "something.txt").touch()
            with self.assertRaises(ValueError):
                check_notebook.get_available_checks()


class TestMain(unittest.TestCase):
    check_names = ["check1", "check_2"]
    script_names = [f"{name}.py" for name in check_names]
    script_contents = [f"print({name})" for name in check_names]

    @contextlib.contextmanager
    def data_dir_setup(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["PLAINBOX_PROVIDER_DATA"] = d
            for script, content in zip(
                self.script_names,
                self.script_contents,
            ):
                (Path(d) / script).write_text(content)
            yield

    @mock.patch(
        "check_notebook.create_parser",
        return_value=argparse.ArgumentParser(),
    )
    def test_creates_parser_with_available_checks(self, mocked):
        with self.data_dir_setup():
            with self.assertRaises(SystemExit):
                check_notebook.main(["--help"])
        mocked.assert_called_once_with(self.check_names)

    @mock.patch("check_notebook.run_script_in_notebook")
    def test_runs_script_content_notebook(self, mocked):
        with self.data_dir_setup():
            for check, content in zip(self.check_names, self.script_contents):
                check_notebook.main(["notebook", check])
                mocked.assert_called_once_with("notebook", content)
                mocked.reset_mock()


class TestRunScriptInNotebook(unittest.TestCase):
    @mock.patch("check_notebook.get_notebook_pod")
    @mock.patch("subprocess.check_call")
    def test_normal_success(self, mocked_run, mocked_pod):
        notebook = "notebook"
        pod_name = "notebokk-xyz"
        script = "import gravity"
        mocked_pod.return_value = pod_name
        check_notebook.run_script_in_notebook(notebook, script)
        with self.subTest("asked for pod"):
            mocked_pod.assert_called_once_with(notebook)
        with self.subTest("asked to run script"):
            cmd = [
                "kubectl",
                "-n",
                "dss",
                "exec",
                pod_name,
                "--",
                "python",
                "-c",
                script,
            ]
            mocked_run.assert_called_once_with(cmd)

    @mock.patch("check_notebook.get_notebook_pod")
    def test_fails_on_missing_pod(self, mocked):
        exception = AssertionError("notebook not found")
        mocked.side_effect = exception
        with self.assertRaises(AssertionError) as caught:
            check_notebook.run_script_in_notebook(
                "notebook",
                "script",
            )
        assert caught.exception == exception

    @mock.patch("check_notebook.get_notebook_pod")
    @mock.patch("subprocess.check_call")
    def test_fails_when_running_script_raises_error(
        self,
        mocked_run,
        mocked_pod,
    ):
        exception = subprocess.CalledProcessError(2, "command")
        mocked_run.side_effect = exception
        mocked_pod.return_value = "pod"
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            check_notebook.run_script_in_notebook(
                "notebook",
                "script",
            )
        assert caught.exception == exception


class TestGetNotebookPod(unittest.TestCase):
    @mock.patch("subprocess.check_output")
    def test_normal_success(self, mocked):
        notebook = "pytorch-test"
        pod = f"{notebook}-77f7b848f5-hfjcn"
        mocked.return_value = f"mlflow-7fcf655ff9-pffk6 {pod}"
        result = check_notebook.get_notebook_pod(notebook)
        with self.subTest("asks for running notebooks"):
            cmd = [
                "kubectl",
                "get",
                "pods",
                "-n",
                "dss",
                "--field-selector=status.phase==Running",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ]
            mocked.assert_called_once_with(cmd, text=True)
        with self.subTest("finds the pod"):
            assert result == pod

    @mock.patch("subprocess.check_output")
    def test_fails_on_failed_run_command(self, mocked):
        exception = subprocess.CalledProcessError(1, "command")
        mocked.side_effect = exception
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            check_notebook.get_notebook_pod("notebook")
        assert caught.exception == exception

    @mock.patch("subprocess.check_output")
    def test_fails_on_missing_pod(self, mocked):
        notebook = "pytorch-test"
        some_other_notebook = "tensorflow-test"
        some_other_pod = f"{some_other_notebook}-77f7b848f5-hfjcn"
        available_pods = f"mlflow-7fcf655ff9-pffk6 {some_other_pod}"
        mocked.return_value = available_pods
        with self.assertRaises(AssertionError) as caught:
            check_notebook.get_notebook_pod(notebook)
        self.assertEqual(
            caught.exception.args,
            (
                f"no RUNNING pod for notebook {notebook} was found",
                f"available pods: {available_pods}",
            ),
        )
