#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Tests for `check_cuda_with_mk8s.py`

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import textwrap
import unittest
from unittest import mock

import check_cuda_with_mk8s


class TestVerifyingValidations(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_normal_success(self, mocked_run):
        mocked_run.return_value = "all validations are successful"
        check_cuda_with_mk8s.has_all_validations_successful()
        mocked_run.assert_called_once_with(
            "kubectl",
            "logs",
            "-n",
            "gpu-operator-resources",
            "-lapp=nvidia-operator-validator",
            "-c",
            "nvidia-operator-validator",
        )

    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_failure_on_bad_exit(self, mocked_run):
        exception = SystemExit(3)
        mocked_run.side_effect = exception
        with self.assertRaises(SystemExit) as caught:
            check_cuda_with_mk8s.has_all_validations_successful()
        assert caught.exception == exception

    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_failure_on_bad_output(self, mocked_run):
        mocked_run.return_value = "garbage"
        with self.assertRaises(AssertionError):
            check_cuda_with_mk8s.has_all_validations_successful()


class TestVerifyingRollout(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.time.sleep")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_normal_success(self, mocked, mocked_sleep):
        daemonset = "something"
        mocked.return_value = f'daemon set "{daemonset}" successfully rolled out'
        check_cuda_with_mk8s.verify_rollout_of_daemonset(daemonset)
        mocked_sleep.assert_called_once_with(10)
        mocked.assert_called_once_with(
            "kubectl",
            "-n",
            "gpu-operator-resources",
            "rollout",
            "status",
            f"ds/{daemonset}",
        )

    @mock.patch("check_cuda_with_mk8s.time.sleep")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_sleeps_before_verifying(self, mocked_run, mocked_sleep):
        daemonset = "something"
        call_order = []

        def tracked_run(*_, **__):
            call_order.append(mocked_run)
            return f'daemon set "{daemonset}" successfully rolled out'

        mocked_run.side_effect = tracked_run
        mocked_sleep.side_effect = lambda *_, **__: call_order.append(mocked_sleep)
        check_cuda_with_mk8s.verify_rollout_of_daemonset(daemonset)
        self.assertListEqual(call_order, [mocked_sleep, mocked_run])

    @mock.patch("check_cuda_with_mk8s.time.sleep")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_fails_on_wrong_output(self, mocked_run, mocked_sleep):
        daemonset = "something"
        mocked_run.return_value = "something completely different"
        with self.assertRaises(AssertionError):
            check_cuda_with_mk8s.verify_rollout_of_daemonset(daemonset)


class TestRollouts(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.verify_rollout_of_daemonset")
    def test_calls_with_correct_daemonset(self, mocked):
        for verification, daemonset in [
            (
                check_cuda_with_mk8s.verify_node_feature_discovery_rollout,
                "gpu-operator-node-feature-discovery-worker",
            ),
            (
                check_cuda_with_mk8s.verify_plugin_rollout,
                "nvidia-device-plugin-daemonset",
            ),
            (
                check_cuda_with_mk8s.verify_validator_rollout,
                "nvidia-operator-validator",
            ),
        ]:
            with self.subTest(daemonset=daemonset):
                mocked.return_value = (
                    f'daemon set "{daemonset}" successfully rolled out'
                )
                verification()
                mocked.assert_called_once_with(daemonset)
                mocked.reset_mock()

    @mock.patch("check_cuda_with_mk8s.verify_rollout_of_daemonset")
    def test_fails_on_exception(self, mocked):
        for i, verification in enumerate(
            [
                check_cuda_with_mk8s.verify_node_feature_discovery_rollout,
                check_cuda_with_mk8s.verify_plugin_rollout,
                check_cuda_with_mk8s.verify_validator_rollout,
            ]
        ):
            with self.subTest(i=i):
                exception = AssertionError()
                mocked.side_effect = exception
                with self.assertRaises(AssertionError) as caught:
                    verification()
                assert caught.exception == exception
                mocked.reset_mock()


class TestVerifyAllRollouts(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.verify_node_feature_discovery_rollout")
    @mock.patch("check_cuda_with_mk8s.verify_plugin_rollout")
    @mock.patch("check_cuda_with_mk8s.verify_validator_rollout")
    def test_calls_are_made_in_expected_order(
        self,
        mocked_validator_rollout,
        mocked_plugin_rollout,
        mocked_discovery_rollout,
    ):
        call_order = []
        mocked_validator_rollout.side_effect = lambda: call_order.append(
            mocked_validator_rollout
        )
        mocked_plugin_rollout.side_effect = lambda: call_order.append(
            mocked_plugin_rollout
        )
        mocked_discovery_rollout.side_effect = lambda: call_order.append(
            mocked_discovery_rollout
        )
        check_cuda_with_mk8s.verify_all_rollouts()
        self.assertListEqual(
            call_order,
            [
                mocked_discovery_rollout,
                mocked_plugin_rollout,
                mocked_validator_rollout,
            ],
        )


class TestEnablingCudaWithOperatorVersion(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_success_when_enabled_for_first_time(self, mocked_run, mocked_rollout):
        mocked_run.return_value = textwrap.dedent(
            """
            Infer repository core for addon gpu
            Enabling NVIDIA GPU
            Addon core/dns is already enabled
            Addon core/helm3 is already enabled
            Using operator GPU driver
            "nvidia" has been added to your repositories
            Hang tight while we grab the latest from your chart repositories...
            ...Successfully got an update from the "nvidia" chart repository
            Update Complete. ⎈Happy Helming!⎈
            NAME: gpu-operator
            LAST DEPLOYED: Thu Feb 13 12:06:04 2025
            NAMESPACE: gpu-operator-resources
            STATUS: deployed
            REVISION: 1
            TEST SUITE: None
            NVIDIA is enabled
            """
        ).strip()
        operator_version = "24.6.2"
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(operator_version)
        mocked_run.assert_called_once_with(
            "sudo",
            "microk8s",
            "enable",
            "gpu",
            "--driver=operator",
            f"--version={operator_version}",
        )
        mocked_rollout.assert_called_once_with()

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_success_when_already_enabled(self, mocked_run, mocked_rollout):
        mocked_run.return_value = textwrap.dedent(
            """
            Infer repository core for addon gpu
            Addon core/gpu is already enabled
            """
        ).strip()
        operator_version = "24.6.2"
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(operator_version)
        mocked_run.assert_called_once_with(
            "sudo",
            "microk8s",
            "enable",
            "gpu",
            "--driver=operator",
            f"--version={operator_version}",
        )
        mocked_rollout.assert_called_once_with()

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_verifying_rollout_is_called_after_enable(self, mocked_run, mocked_rollout):
        call_order = []

        def tracking_run(*_, **__):
            call_order.append(mocked_run)
            return "Addon core/gpu is already enabled"

        mocked_run.side_effect = tracking_run
        mocked_rollout.side_effect = lambda: call_order.append(mocked_rollout)
        operator_version = "24.6.2"
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(operator_version)
        self.assertListEqual(call_order, [mocked_run, mocked_rollout])

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_fails_on_bad_exit_from_command(self, mocked_run, mocked_rollout):
        exception = SystemExit(8)
        mocked_run.side_effect = exception
        operator_version = "24.6.2"
        with self.assertRaises(SystemExit) as caught:
            check_cuda_with_mk8s.can_be_enabled_with_operator_version(operator_version)
        assert caught.exception == exception

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_fails_on_failed_rollout_verification(self, mocked_run, mocked_rollout):
        exception = AssertionError()
        mocked_run.return_value = "NVIDIA is enabled"
        mocked_rollout.side_effect = exception
        operator_version = "24.6.2"
        with self.assertRaises(AssertionError) as caught:
            check_cuda_with_mk8s.can_be_enabled_with_operator_version(operator_version)
        assert caught.exception == exception
