#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Tests for `check_dss.py`

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import textwrap
import unittest
from unittest import mock

import check_notebook


class TestArgumentParsing(unittest.TestCase):
    @mock.patch("check_notebook.create_parser_with_checks_as_commands")
    def test_expected_checks_are_used_for_parser(self, mocked):
        check_notebook.parse_args()
        mocked.assert_called_once_with(
            [
                check_notebook.has_pytorch_available,
                check_notebook.has_tensorflow_available,
                check_notebook.can_use_intel_gpu_in_pytorch,
                check_notebook.can_use_intel_gpu_in_tensorflow,
                check_notebook.can_use_nvidia_gpu_in_pytorch,
                check_notebook.can_use_nvidia_gpu_in_tensorflow,
            ],
            description="Check notebooks in DSS",
        )

    @mock.patch("check_notebook.run_command")
    def test_parser_accepts_timeout(self, mocked):
        mocked.return_value = check_notebook.SUCCESS_MARKER
        parsed = check_notebook.parse_args(
            ["--timeout", "3.5", "has_pytorch_available", "test-notebook"]
        )
        assert parsed["timeout"] == 3.5


class TestRunCommand(unittest.TestCase):
    @mock.patch("check_notebook.common_run_command")
    def test_calls_common_run_command(self, mocked):
        mocked.return_value = "expected"
        result = check_notebook.run_command("ls", "-lah")
        with self.subTest("mock was called"):
            mocked.assert_called_once()
        with self.subTest("result was as expected"):
            assert result == "expected"

    @mock.patch("check_notebook.common_run_command")
    def test_calls_with_default_timeout(self, mocked):
        check_notebook.run_command("ls", "-lah")
        mocked.assert_called_once_with(
            "ls", "-lah", timeout=check_notebook._TIMEOUT_SEC
        )

    @mock.patch("check_notebook.common_run_command")
    def test_calls_with_given_timeout(self, mocked):
        orig_timeout = check_notebook._TIMEOUT_SEC
        try:
            timeout = 1010101
            assert timeout != orig_timeout
            check_notebook.run_command("ls", "-lah", timeout=timeout)
            mocked.assert_called_once_with("ls", "-lah", timeout=timeout)
        finally:
            check_notebook._TIMEOUT_SEC = orig_timeout


class TestMain(unittest.TestCase):
    @mock.patch("check_notebook.script_must_succeed_in_notebook")
    def test_sets_global_timeout(self, mocked):
        orig_timeout = check_notebook._TIMEOUT_SEC
        try:
            timeout = 1010101
            assert timeout != orig_timeout
            check_notebook.main(
                ["--timeout", str(timeout), "has_pytorch_available", "notebook"]
            )
            assert check_notebook._TIMEOUT_SEC == timeout
        finally:
            check_notebook._TIMEOUT_SEC = orig_timeout

    @mock.patch("check_notebook.script_must_succeed_in_notebook")
    def test_calls_appropriate_check(self, mocked_run):
        check_notebook.main(["has_pytorch_available", "notebook"])
        mocked_run.assert_called_once_with(
            "notebook", check_notebook.SCRIPT["pytorch_is_available"]
        )


class TestScriptMustSucceedInNotebook(unittest.TestCase):
    @mock.patch("check_notebook.pod_for_running_notebook")
    @mock.patch("check_notebook.run_script_in_pod")
    def test_normal_success(self, mocked_run, mocked_pod):
        notebook = "notebook"
        pod_name = "notebokk-xyz"
        script = "import gravity"
        mocked_pod.return_value = pod_name
        mocked_run.return_value = check_notebook.SUCCESS_MARKER
        check_notebook.script_must_succeed_in_notebook(notebook, script)
        with self.subTest("asked for pod"):
            mocked_pod.assert_called_once_with(notebook)
        with self.subTest("asked to run script"):
            mocked_run.assert_called_once_with(pod_name, script)

    @mock.patch("check_notebook.pod_for_running_notebook")
    def test_fails_on_missing_pod(self, mocked):
        exception = AssertionError("notebook not found")
        mocked.side_effect = exception
        with self.assertRaises(AssertionError) as caught:
            check_notebook.script_must_succeed_in_notebook("notebook", "script")
        assert caught.exception == exception

    @mock.patch("check_notebook.pod_for_running_notebook")
    @mock.patch("check_notebook.run_script_in_pod")
    def test_fails_when_running_script_gives_bad_exit_code(
        self, mocked_run, mocked_pod
    ):
        exception = SystemExit(2)
        mocked_run.side_effect = exception
        mocked_pod.return_value = "pod"
        with self.assertRaises(SystemExit) as caught:
            check_notebook.script_must_succeed_in_notebook("notebook", "script")
        assert caught.exception.code == 2

    @mock.patch("check_notebook.pod_for_running_notebook")
    @mock.patch("check_notebook.run_script_in_pod")
    def test_fails_when_running_script_does_not_have_success_marker(
        self, mocked_run, mocked_pod
    ):
        garbage_result = "garbage"
        assert check_notebook.SUCCESS_MARKER not in garbage_result
        mocked_run.return_value = garbage_result
        mocked_pod.return_value = "pod"
        with self.assertRaises(AssertionError) as caught:
            check_notebook.script_must_succeed_in_notebook("notebook", "script")
        assert (
            caught.exception.args[0]
            == f"{check_notebook.SUCCESS_MARKER} not in results"
        )


class TestPodForRunningNotebook(unittest.TestCase):
    @mock.patch("check_notebook.run_command")
    def test_normal_success(self, mocked):
        notebook = "pytorch-test"
        pod = f"{notebook}-77f7b848f5-hfjcn"
        mocked.return_value = textwrap.dedent(
            f"""
            NAME                            READY   STATUS    RESTARTS   AGE
            mlflow-7fcf655ff9-pffk6         1/1     Running   0          6m43s
            {pod}                           1/1     Running   0          5m27s
            """
        )
        result = check_notebook.pod_for_running_notebook(notebook)
        with self.subTest("asks for running notebooks"):
            mocked.assert_called_once_with(
                "kubectl",
                "get",
                "pods",
                "-n",
                "dss",
                "--field-selector=status.phase==Running",
            )
        with self.subTest("finds the pod"):
            assert result == pod

    @mock.patch("check_notebook.run_command")
    def test_fails_on_bad_exit_from_run_command(self, mocked):
        mocked.side_effect = SystemExit(1)
        with self.assertRaises(SystemExit) as caught:
            check_notebook.pod_for_running_notebook("notebook")
        assert caught.exception.code == 1

    @mock.patch("check_notebook.run_command")
    def test_fails_on_missing_pod(self, mocked):
        notebook = "pytorch-test"
        some_other_notebook = "tensorflow-test"
        some_other_pod = f"{some_other_notebook}-77f7b848f5-hfjcn"
        mocked.return_value = textwrap.dedent(
            f"""
            NAME                            READY   STATUS    RESTARTS   AGE
            mlflow-7fcf655ff9-pffk6         1/1     Running   0          6m43s
            {some_other_pod}                           1/1     Running   0          5m27s
            """
        )
        with self.assertRaises(AssertionError) as caught:
            check_notebook.pod_for_running_notebook(notebook)
        assert (
            caught.exception.args[0]
            == f"no RUNNING pod for notebook {notebook} was found"
        )


class TestRunScriptInPod(unittest.TestCase):
    @mock.patch("check_notebook.run_command")
    def test_normal_success(self, mocked):
        mocked.return_value = "expected"
        result = check_notebook.run_script_in_pod("pod", "script")
        with self.subTest("runs expected command"):
            mocked.assert_called_once_with(
                "kubectl", "-n", "dss", "exec", "pod", "--", "python", "-c", "script"
            )
        with self.subTest("returns expected value"):
            assert result == "expected"

    @mock.patch("check_notebook.run_command")
    def test_fails_on_bad_exit_from_run_command(self, mocked):
        mocked.side_effect = SystemExit(1)
        with self.assertRaises(SystemExit) as caught:
            check_notebook.run_script_in_pod("pod", "script")
        assert caught.exception.code == 1


class TestCommands(unittest.TestCase):
    @mock.patch("check_notebook.script_must_succeed_in_notebook")
    def test_asks_to_run_expected_script(self, mocked):
        notebook = "notebook"
        for i, (check, script_name) in enumerate(
            [
                (check_notebook.has_pytorch_available, "pytorch_is_available"),
                (check_notebook.has_tensorflow_available, "tensorflow_is_available"),
                (
                    check_notebook.can_use_intel_gpu_in_pytorch,
                    "pytorch_can_use_intel_gpu",
                ),
                (
                    check_notebook.can_use_intel_gpu_in_tensorflow,
                    "tensorflow_can_use_intel_gpu",
                ),
                (
                    check_notebook.can_use_nvidia_gpu_in_pytorch,
                    "pytorch_can_use_nvidia_gpu",
                ),
                (
                    check_notebook.can_use_nvidia_gpu_in_tensorflow,
                    "tensorflow_can_use_nvidia_gpu",
                ),
            ]
        ):
            with self.subTest(i=i):
                check(notebook)
                mocked.assert_called_once_with(
                    notebook, check_notebook.SCRIPT[script_name]
                )
                mocked.reset_mock()

    @mock.patch("check_notebook.script_must_succeed_in_notebook")
    def test_fails_on_failure(self, mocked):
        notebook = "notebook"
        for i, check in enumerate(
            [
                check_notebook.has_pytorch_available,
                check_notebook.has_tensorflow_available,
                check_notebook.can_use_intel_gpu_in_pytorch,
                check_notebook.can_use_intel_gpu_in_tensorflow,
                check_notebook.can_use_nvidia_gpu_in_pytorch,
                check_notebook.can_use_nvidia_gpu_in_tensorflow,
            ]
        ):
            with self.subTest(i=i):
                exception = AssertionError("missing success marker")
                mocked.side_effect = exception
                with self.assertRaises(AssertionError) as caught:
                    check(notebook)
                assert caught.exception == exception
                mocked.reset_mock()
