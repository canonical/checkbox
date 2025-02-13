#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Tests for `check_dss.py`

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import os
import textwrap
import unittest
from unittest import mock

import check_dss


GARBAGE_OUTPUTS = [
    "what's happening?",
    "ahostnahlwdrth nahlsreu tlahwrtn hlarsnth larnwdhtlrnavhaoser nthl",
]


class TestRunCommand(unittest.TestCase):
    @mock.patch("check_dss.common_run_command")
    def test_calls_common_run_command(self, mocked):
        mocked.return_value = "expected"
        result = check_dss.run_command("ls", "-lah")
        with self.subTest("mock was called"):
            mocked.assert_called_once()
        with self.subTest("result was as expected"):
            assert result == "expected"

    @mock.patch("check_dss.common_run_command")
    def test_calls_with_default_timeout(self, mocked):
        check_dss.run_command("ls", "-lah")
        mocked.assert_called_once_with(
            "ls", "-lah", timeout=check_dss._TIMEOUT_SEC, env=mock.ANY, cwd=mock.ANY
        )

    @mock.patch("check_dss.common_run_command")
    def test_calls_with_env_without_python_vars(self, mocked):
        check_dss.run_command("ls", "-lah")
        sent_kwargs = mocked.call_args.kwargs
        passed_env = sent_kwargs["env"]
        with self.subTest("env must not have PYTHONPATH"):
            assert "PYTHONPATH" not in passed_env
        with self.subTest("env must not have PYTHONHOME"):
            assert "PYTHONHOME" not in passed_env
        with self.subTest("env must not have PYTHONUSERBASE"):
            assert "PYTHONUSERBASE" not in passed_env

    @mock.patch("check_dss.common_run_command")
    def test_calls_with_cwd_set_to_home(self, mocked):
        orig_home = os.environ["HOME"]
        check_dss.run_command("ls", "-lah")
        sent_kwargs = mocked.call_args.kwargs
        passed_cwd = sent_kwargs["cwd"]
        assert passed_cwd == orig_home

    @mock.patch("check_dss.common_run_command")
    def test_calls_with_given_timeout(self, mocked):
        orig_timeout = check_dss._TIMEOUT_SEC
        try:
            timeout = 1010101
            assert timeout != orig_timeout
            check_dss.run_command("ls", "-lah", timeout=timeout)
            mocked.assert_called_once_with(
                "ls", "-lah", timeout=timeout, env=mock.ANY, cwd=mock.ANY
            )
        finally:
            check_dss._TIMEOUT_SEC = orig_timeout


class TestArgumentParsing(unittest.TestCase):
    @mock.patch("check_dss.create_parser_with_checks_as_commands")
    def test_expected_checks_are_used_for_parser(self, mocked):
        check_dss.parse_args()
        mocked.assert_called_once_with(
            [
                check_dss.can_be_initialized,
                check_dss.can_be_purged,
                check_dss.has_mlflow_ready,
                check_dss.has_intel_gpu_acceleration_enabled,
                check_dss.has_nvidia_gpu_acceleration_enabled,
                check_dss.can_create_notebook,
                check_dss.can_start_removing_notebook,
            ],
            description="Run and check 'dss' commands",
        )

    @mock.patch("check_dss.run_command")
    def test_parser_accepts_timeout(self, mocked):
        mocked.return_value = "DSS initialized"
        parsed = check_dss.parse_args(
            ["--timeout", "3.5", "can_be_initialized", "config"]
        )
        assert parsed["timeout"] == 3.5


class TestMain(unittest.TestCase):
    @mock.patch("check_dss.common_run_command")
    def test_sets_global_timeout(self, mocked):
        orig_timeout = check_dss._TIMEOUT_SEC
        try:
            timeout = 1010101
            assert timeout != orig_timeout
            mocked.return_value = "DSS initialized"
            check_dss.main(["--timeout", str(timeout), "can_be_initialized", "config"])
            assert check_dss._TIMEOUT_SEC == timeout
        finally:
            check_dss._TIMEOUT_SEC = orig_timeout

    @mock.patch("check_dss.run_command")
    def test_calls_appropriate_check(self, mocked):
        mocked.return_value = "DSS initialized"
        check_dss.main(["can_be_initialized", "config"])
        mocked.assert_called_once_with("dss", "initialize", "--kubeconfig", "config")


class TestDssInitialize(unittest.TestCase):
    valid_kubeconfig_value = textwrap.dedent(
        """
        config: "valid_value"
        """
    )

    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        mocked.return_value = textwrap.dedent(
            """
            Executing initialize command
            Storing provided kubeconfig to /home/user/.dss/config
            Waiting for deployment mlflow in namespace dss to be ready...
            Deployment mlflow in namespace dss is ready
            DSS initialized. To create your first notebook run the command:

            dss create

            Examples:
              dss create my-notebook --image=pytorch
              dss create my-notebook --image=kubeflownotebookswg/jupyter-scipy:v1.8.0
            """
        )
        check_dss.can_be_initialized(self.valid_kubeconfig_value)
        mocked.assert_called_once_with(
            "dss", "initialize", "--kubeconfig", self.valid_kubeconfig_value
        )

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(5)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.can_be_initialized(self.valid_kubeconfig_value)
        assert caught.exception.code == 5

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        for i, garbage in enumerate(GARBAGE_OUTPUTS):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.can_be_initialized(self.valid_kubeconfig_value)


class TestDssPurge(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        mocked.return_value = textwrap.dedent(
            """
            Waiting for namespace dss to be deleted...
            Waiting for namespace dss to be deleted...
            Waiting for namespace dss to be deleted...
            Waiting for namespace dss to be deleted...
            Waiting for namespace dss to be deleted...
            Success: All DSS components and notebooks purged successfully from the Kubernetes cluster.
            """
        )
        check_dss.can_be_purged()
        mocked.assert_called_once_with("dss", "purge")

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(5)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.can_be_purged()
        assert caught.exception.code == 5

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        for i, garbage in enumerate(GARBAGE_OUTPUTS):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.can_be_purged()


NORMAL_DSS_STATUS_NO_GPUS = textwrap.dedent(
    """
    MLflow deployment: Ready
    MLflow URL: http://localhost:5000
    NVIDIA GPU acceleration: Disabled
    Intel GPU acceleration: Disabled
    """
)
NORMAL_DSS_STATUS_ONLY_INTEL_GPU = textwrap.dedent(
    """
    MLflow deployment: Ready
    MLflow URL: http://localhost:5000
    NVIDIA GPU acceleration: Disabled
    Intel GPU acceleration: Enabled
    """
)
NORMAL_DSS_STATUS_ONLY_NVIDIA_GPU = textwrap.dedent(
    """
    MLflow deployment: Ready
    MLflow URL: http://localhost:5000
    NVIDIA GPU acceleration: Enabled
    Intel GPU acceleration: Disable
    """
)
NORMAL_DSS_STATUS_BOTH_GPUS = textwrap.dedent(
    """
    MLflow deployment: Ready
    MLflow URL: http://localhost:5000
    NVIDIA GPU acceleration: Enabled
    Intel GPU acceleration: Enabled
    """
)
NORMAL_DSS_STATUS_VALUES = [
    NORMAL_DSS_STATUS_NO_GPUS,
    NORMAL_DSS_STATUS_ONLY_INTEL_GPU,
    NORMAL_DSS_STATUS_ONLY_NVIDIA_GPU,
    NORMAL_DSS_STATUS_BOTH_GPUS,
]


class TestDssHasMlflow(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        for i, normal_response in enumerate(NORMAL_DSS_STATUS_VALUES):
            with self.subTest(i=i):
                mocked.return_value = normal_response
                check_dss.has_mlflow_ready()
                mocked.assert_called_with("dss", "status")
                mocked.reset_mock()

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(1)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.has_mlflow_ready()
        assert caught.exception.code == 1

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        for i, garbage in enumerate(
            [
                *GARBAGE_OUTPUTS,
                "MLFlow deployment: Ready",  # wrong capitalisation
                "MLflow deployment: Starting",
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.has_mlflow_ready()


class TestDssHasIntelGpu(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        for i, normal_response in enumerate(
            [
                NORMAL_DSS_STATUS_ONLY_INTEL_GPU,
                NORMAL_DSS_STATUS_BOTH_GPUS,
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = normal_response
                check_dss.has_intel_gpu_acceleration_enabled()
                mocked.assert_called_with("dss", "status")
                mocked.reset_mock()

    @mock.patch("check_dss.run_command")
    def test_normal_failure(self, mocked):
        for i, normal_response in enumerate(
            [
                NORMAL_DSS_STATUS_ONLY_NVIDIA_GPU,
                NORMAL_DSS_STATUS_NO_GPUS,
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = normal_response
                with self.assertRaises(AssertionError):
                    check_dss.has_intel_gpu_acceleration_enabled()
                mocked.assert_called_with("dss", "status")
                mocked.reset_mock()

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(1)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.has_intel_gpu_acceleration_enabled()
        assert caught.exception.code == 1

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        for i, garbage in enumerate(
            [
                *GARBAGE_OUTPUTS,
                "Intel XPU acceleration: Enabled",
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.has_intel_gpu_acceleration_enabled()


class TestDssHasNvidiaGpu(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        for i, normal_response in enumerate(
            [
                NORMAL_DSS_STATUS_ONLY_NVIDIA_GPU,
                NORMAL_DSS_STATUS_BOTH_GPUS,
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = normal_response
                check_dss.has_nvidia_gpu_acceleration_enabled()
                mocked.assert_called_with("dss", "status")
                mocked.reset_mock()

    @mock.patch("check_dss.run_command")
    def test_normal_failure(self, mocked):
        for i, normal_response in enumerate(
            [
                NORMAL_DSS_STATUS_ONLY_INTEL_GPU,
                NORMAL_DSS_STATUS_NO_GPUS,
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = normal_response
                with self.assertRaises(AssertionError):
                    check_dss.has_nvidia_gpu_acceleration_enabled()
                mocked.assert_called_with("dss", "status")
                mocked.reset_mock()

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(1)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.has_nvidia_gpu_acceleration_enabled()
        assert caught.exception.code == 1

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        for i, garbage in enumerate(
            [
                *GARBAGE_OUTPUTS,
                "Nvidia GPU acceleration: Enabled",
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.has_nvidia_gpu_acceleration_enabled()


class TestDssCreatingNotebook(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        name = "pytorch-notebook-cuda"
        image = "pytorch-cuda"
        normal_response = textwrap.dedent(
            f"""
            Executing create command
            Waiting for deployment {name} in namespace dss to be ready...
            Deployment pytorch in namespace dss is ready
            Success: Notebook {name} created successfully.
            Access the notebook at http://localhost:80.
            """
        )
        mocked.return_value = normal_response
        check_dss.can_create_notebook(name, image)
        mocked.assert_called_with("dss", "create", name, "--image", image)

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(7)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.can_create_notebook("tensorflow", "tensorflow-intel")
        assert caught.exception.code == 7

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        notebook_name = "playground"
        image = "tensorflow-intel"
        some_other_notebook_name = "numpy"
        for i, garbage in enumerate(
            [
                *GARBAGE_OUTPUTS,
                "",
                textwrap.dedent(
                    f"""
                    Executing create command
                    Waiting for deployment {some_other_notebook_name} in namespace dss to be ready...
                    Deployment pytorch in namespace dss is ready
                    Success: Notebook {some_other_notebook_name} created successfully.
                    Access the notebook at http://localhost:80.
                    """
                ),
                textwrap.dedent(
                    f"""
                    Executing create command
                    [ERROR] Failed to create Notebook. Notebook with name '{notebook_name}' already exists.
                    Please specify a different name.
                    [ERROR] Failed to get the URL of notebook name with error code 404.
                    """
                ),
                textwrap.dedent(
                    f"""
                    Executing create command
                    Waiting for deployment {notebook_name} in namespace dss to be ready...

                    Aborted!
                    """
                ),
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.can_create_notebook(notebook_name, image)


class TestDssRemovingNotebook(unittest.TestCase):
    @mock.patch("check_dss.run_command")
    def test_normal_success(self, mocked):
        name = "pytorch-notebook-cuda"
        normal_response = textwrap.dedent(
            f"""
            Executing remove command
            Removing the notebook {name}. Check `dss list` for the status of the notebook.
            """
        )
        mocked.return_value = normal_response
        check_dss.can_start_removing_notebook(name)
        mocked.assert_called_with("dss", "remove", name)

    @mock.patch("check_dss.run_command")
    def test_failure_on_bad_exit_code(self, mocked):
        expected_exceptinon = SystemExit(7)
        mocked.side_effect = expected_exceptinon
        with self.assertRaises(SystemExit) as caught:
            check_dss.can_start_removing_notebook("tensorflow")
        assert caught.exception.code == 7

    @mock.patch("check_dss.run_command")
    def test_failure_on_wrong_response(self, mocked):
        notebook_name = "playground"
        some_other_notebook_name = "numpy"
        for i, garbage in enumerate(
            [
                *GARBAGE_OUTPUTS,
                textwrap.dedent(
                    f"""
                    Executing remove command
                    Removing the notebook {some_other_notebook_name}. Check `dss list` for the status of the notebook.
                    """
                ),
            ]
        ):
            with self.subTest(i=i):
                mocked.return_value = garbage
                with self.assertRaises(AssertionError):
                    check_dss.can_start_removing_notebook(notebook_name)
