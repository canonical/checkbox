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
"""Tests for `check_cuda_with_mk8s.py`"""

import subprocess
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
    def test_failure_on_failed_run_command(self, mocked_run):
        exception = subprocess.CalledProcessError(3, "command")
        mocked_run.side_effect = exception
        with self.assertRaises(subprocess.CalledProcessError) as caught:
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
        ds = "something"
        mocked.return_value = f'daemon set "{ds}" successfully rolled out'
        check_cuda_with_mk8s.verify_rollout_of_daemonset(ds)
        mocked_sleep.assert_called_once_with(10)
        mocked.assert_called_once_with(
            "kubectl",
            "-n",
            "gpu-operator-resources",
            "rollout",
            "status",
            f"ds/{ds}",
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
        mocked_sleep.side_effect = lambda *_, **__: call_order.append(
            mocked_sleep,
        )
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
    def test_success_when_enabled_for_first_time_mk8s_1_28(
        self,
        mocked_run,
        mocked_rollout,
    ):
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
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(
            operator_version,
        )
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
    def test_success_when_enabled_for_first_time_mk8s_1_31(
        self,
        mocked_run,
        mocked_rollout,
    ):
        mocked_run.return_value = textwrap.dedent(
            """
            Infer repository core for addon gpu

            WARNING: The gpu addon has been renamed to nvidia.

            Please use 'microk8s enable nvidia' instead.


            Addon core/dns is already enabled
            Addon core/helm3 is already enabled
            WARNING: --driver is deprecated, please use --gpu-operator-driver instead
            WARNING: --version is deprecated, please use --gpu-operator-version instead
            "nvidia" has been added to your repositories
            Hang tight while we grab the latest from your chart repositories...
            ...Successfully got an update from the "nvidia" chart repository
            Update Complete. ⎈Happy Helming!⎈
            Deploy NVIDIA GPU operator
            Using operator GPU driver
            W0214 10:02:01.391895   75846 warnings.go:70] spec.template.spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution[0].preference.matchExpressions[0].key: node-role.kubernetes.io/master is use "node-role.kubernetes.io/control-plane" instead
            W0214 10:02:01.406554   75846 warnings.go:70] spec.template.spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution[0].preference.matchExpressions[0].key: node-role.kubernetes.io/master is use "node-role.kubernetes.io/control-plane" instead
            NAME: gpu-operator
            LAST DEPLOYED: Fri Feb 14 10:02:00 2025
            NAMESPACE: gpu-operator-resources
            STATUS: deployed
            REVISION: 1
            TEST SUITE: None
            Deployed NVIDIA GPU operator
            """
        ).strip()
        operator_version = "24.6.2"
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(
            operator_version,
        )
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
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(
            operator_version,
        )
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
    def test_verifying_rollout_is_called_after_enable(
        self,
        mocked_run,
        mocked_rollout,
    ):
        call_order = []

        def tracking_run(*_, **__):
            call_order.append(mocked_run)
            return "Addon core/gpu is already enabled"

        mocked_run.side_effect = tracking_run
        mocked_rollout.side_effect = lambda: call_order.append(mocked_rollout)
        operator_version = "24.6.2"
        check_cuda_with_mk8s.can_be_enabled_with_operator_version(
            operator_version,
        )
        self.assertListEqual(call_order, [mocked_run, mocked_rollout])

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_fails_on_failed_run_command(self, mocked_run, mocked_rollout):
        exception = subprocess.CalledProcessError(1, "command")
        mocked_run.side_effect = exception
        operator_version = "24.6.2"
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            check_cuda_with_mk8s.can_be_enabled_with_operator_version(
                operator_version,
            )
        assert caught.exception == exception

    @mock.patch("check_cuda_with_mk8s.verify_all_rollouts")
    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_fails_on_failed_rollout_verification(
        self,
        mocked_run,
        mocked_rollout,
    ):
        exception = AssertionError()
        mocked_run.return_value = "NVIDIA is enabled"
        mocked_rollout.side_effect = exception
        operator_version = "24.6.2"
        with self.assertRaises(AssertionError) as caught:
            check_cuda_with_mk8s.can_be_enabled_with_operator_version(
                operator_version,
            )
        assert caught.exception == exception


class TestArgumentParsingAndMain(unittest.TestCase):
    @mock.patch("check_cuda_with_mk8s.create_parser_with_checks_as_commands")
    def test_expected_checks_are_used_for_parser(self, mocked):
        check_cuda_with_mk8s.parse_args()
        mocked.assert_called_once_with(
            [
                check_cuda_with_mk8s.can_be_enabled_with_operator_version,
                check_cuda_with_mk8s.has_all_validations_successful,
            ],
            description="Check enabling CUDA with microk8s",
        )

    @mock.patch("check_cuda_with_mk8s.run_command")
    def test_main_calls_appropriate_check(self, mocked):
        mocked.return_value = "all validations are successful"
        check_cuda_with_mk8s.main(["has_all_validations_successful"])
        mocked.assert_called_once_with(
            "kubectl",
            "logs",
            "-n",
            "gpu-operator-resources",
            "-lapp=nvidia-operator-validator",
            "-c",
            "nvidia-operator-validator",
        )
