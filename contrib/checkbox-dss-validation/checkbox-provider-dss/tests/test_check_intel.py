#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Tests for `check_intel.py`

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import subprocess
import unittest
from unittest import mock

import check_intel


class TestVerifyingRollout(unittest.TestCase):
    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_normal_success(self, mocked, mocked_sleep):
        ds = "something"
        ns = "whatever"
        mocked.return_value = f'daemon set "{ds}" successfully rolled out'
        check_intel.verify_rollout_of_daemonset(ds, ns)
        mocked_sleep.assert_called_once_with(10)
        mocked.assert_called_once_with(
            "kubectl",
            "-n",
            ns,
            "rollout",
            "status",
            f"ds/{ds}",
        )

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_sleeps_before_verifying(self, mocked_run, mocked_sleep):
        daemonset = "something"
        namespace = "whatever"
        call_order = []

        def tracked_run(*_, **__):
            call_order.append(mocked_run)
            return f'daemon set "{daemonset}" successfully rolled out'

        mocked_run.side_effect = tracked_run
        mocked_sleep.side_effect = lambda *_, **__: call_order.append(
            mocked_sleep,
        )
        check_intel.verify_rollout_of_daemonset(daemonset, namespace)
        self.assertListEqual(call_order, [mocked_sleep, mocked_run])

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_fails_on_wrong_output(self, mocked_run, mocked_sleep):
        daemonset = "something"
        namespace = "namespace"
        mocked_run.return_value = "something completely different"
        with self.assertRaises(AssertionError):
            check_intel.verify_rollout_of_daemonset(daemonset, namespace)


class TestRollouts(unittest.TestCase):
    @mock.patch("check_intel.verify_rollout_of_daemonset")
    def test_calls_with_correct_daemonset(self, mocked):
        for verification, daemonset, namespace in [
            (
                check_intel.verify_nfd_worker_rollout,
                "nfd-worker",
                "node-feature-discovery",
            ),
            (
                check_intel.verify_plugin_rollout,
                "intel-gpu-plugin",
                "default",
            ),
        ]:
            with self.subTest(daemonset=daemonset):
                mocked.return_value = (
                    f'daemon set "{daemonset}" successfully rolled out'
                )
                verification()
                mocked.assert_called_once_with(daemonset, namespace)
                mocked.reset_mock()

    @mock.patch("check_intel.verify_rollout_of_daemonset")
    def test_fails_on_exception(self, mocked):
        for i, verification in enumerate(
            [
                check_intel.verify_nfd_worker_rollout,
                check_intel.verify_plugin_rollout,
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
    @mock.patch("check_intel.verify_nfd_worker_rollout")
    @mock.patch("check_intel.verify_plugin_rollout")
    def test_calls_are_made_in_expected_order(
        self,
        mocked_plugin_rollout,
        mocked_discovery_rollout,
    ):
        call_order = []
        mocked_plugin_rollout.side_effect = lambda: call_order.append(
            mocked_plugin_rollout
        )
        mocked_discovery_rollout.side_effect = lambda: call_order.append(
            mocked_discovery_rollout
        )
        check_intel.verify_all_rollouts()
        self.assertListEqual(
            call_order,
            [
                mocked_discovery_rollout,
                mocked_plugin_rollout,
            ],
        )


class TestEnablingIntelWithPluginVersion(unittest.TestCase):
    plugin_version = "v0.30.0"

    @mock.patch("check_intel.verify_all_rollouts")
    @mock.patch("check_intel.run_command")
    def test_success(self, mocked_run, mocked_rollout):
        mocked_run.return_value = check_intel.SUCCESS_MARKER
        check_intel.can_be_enabled_with_plugin_version(self.plugin_version)
        mocked_run.assert_called_once_with(
            "enable_intel.sh",
            self.plugin_version,
            str(check_intel.SLOTS_PER_GPU),
        )
        mocked_rollout.assert_called_once_with()

    @mock.patch("check_intel.verify_all_rollouts")
    @mock.patch("check_intel.run_command")
    def test_verifying_rollout_is_called_after_enable(
        self,
        mocked_run,
        mocked_rollout,
    ):
        call_order = []

        def tracking_run(*_, **__):
            call_order.append(mocked_run)
            return check_intel.SUCCESS_MARKER

        mocked_run.side_effect = tracking_run
        mocked_rollout.side_effect = lambda: call_order.append(mocked_rollout)
        check_intel.can_be_enabled_with_plugin_version(self.plugin_version)
        self.assertListEqual(call_order, [mocked_run, mocked_rollout])

    @mock.patch("check_intel.verify_all_rollouts")
    @mock.patch("check_intel.run_command")
    def test_fails_on_failed_run_command(self, mocked_run, mocked_rollout):
        exception = subprocess.CalledProcessError(1, "command")
        mocked_run.side_effect = exception
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            check_intel.can_be_enabled_with_plugin_version(self.plugin_version)
        assert caught.exception == exception

    @mock.patch("check_intel.verify_all_rollouts")
    @mock.patch("check_intel.run_command")
    def test_fails_on_failed_rollout_verification(
        self,
        mocked_run,
        mocked_rollout,
    ):
        exception = AssertionError()
        mocked_run.return_value = check_intel.SUCCESS_MARKER
        mocked_rollout.side_effect = exception
        with self.assertRaises(AssertionError) as caught:
            check_intel.can_be_enabled_with_plugin_version(self.plugin_version)
        assert caught.exception == exception


class TestHasEnoughCapacitySlots(unittest.TestCase):
    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_normal_success(self, mocked_run, mocked_sleep):
        for i in range(1, 4):
            with self.subTest(i=i):
                mocked_run.return_value = f"'{check_intel.SLOTS_PER_GPU * i}'"
                check_intel.has_enough_capacity_slots()
                mocked_sleep.assert_called_once_with(10)
                mocked_run.assert_called_once_with(
                    "kubectl",
                    "get",
                    "node",
                    "-o",
                    "jsonpath='{.items[0].status.capacity.gpu\\.intel\\.com/i915}'",
                )
                mocked_run.reset_mock()
                mocked_sleep.reset_mock()

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_sleeps_before_running(self, mocked_run, mocked_sleep):
        call_order = []

        def tracked_run(*_, **__):
            call_order.append(mocked_run)
            return f"'{check_intel.SLOTS_PER_GPU}'"

        mocked_run.side_effect = tracked_run
        mocked_sleep.side_effect = lambda *_, **__: call_order.append(
            mocked_sleep,
        )
        check_intel.has_enough_capacity_slots()
        self.assertListEqual(call_order, [mocked_sleep, mocked_run])

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_fails_on_wrong_output(self, mocked_run, mocked_sleep):
        mocked_run.return_value = "''"
        with self.assertRaises(AssertionError):
            check_intel.has_enough_capacity_slots()


class TestHasEnoughAllocatableSlots(unittest.TestCase):
    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_normal_success(self, mocked_run, mocked_sleep):
        for i in range(1, 4):
            with self.subTest(i=i):
                mocked_run.return_value = f"'{check_intel.SLOTS_PER_GPU * i}'"
                check_intel.has_enough_allocatable_slots()
                mocked_sleep.assert_called_once_with(10)
                mocked_run.assert_called_once_with(
                    "kubectl",
                    "get",
                    "node",
                    "-o",
                    "jsonpath='{.items[0].status.allocatable.gpu\\.intel\\.com/i915}'",
                )
                mocked_run.reset_mock()
                mocked_sleep.reset_mock()

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_sleeps_before_running(self, mocked_run, mocked_sleep):
        call_order = []

        def tracked_run(*_, **__):
            call_order.append(mocked_run)
            return f"'{check_intel.SLOTS_PER_GPU}'"

        mocked_run.side_effect = tracked_run
        mocked_sleep.side_effect = lambda *_, **__: call_order.append(
            mocked_sleep,
        )
        check_intel.has_enough_allocatable_slots()
        self.assertListEqual(call_order, [mocked_sleep, mocked_run])

    @mock.patch("check_intel.time.sleep")
    @mock.patch("check_intel.run_command")
    def test_fails_on_wrong_output(self, mocked_run, mocked_sleep):
        mocked_run.return_value = "''"
        with self.assertRaises(AssertionError):
            check_intel.has_enough_allocatable_slots()


class TestArgumentParsingAndMain(unittest.TestCase):
    @mock.patch("check_intel.create_parser_with_checks_as_commands")
    def test_expected_checks_are_used_for_parser(self, mocked):
        check_intel.parse_args()
        mocked.assert_called_once_with(
            [
                check_intel.can_be_enabled_with_plugin_version,
                check_intel.node_label_is_attached,
                check_intel.has_enough_capacity_slots,
                check_intel.has_enough_allocatable_slots,
            ],
            description="Check enabling Intel GPU acceleration in Kubernetes",
        )

    @mock.patch("check_intel.run_command")
    def test_main_calls_appropriate_check(self, mocked):
        mocked.return_value = "true"
        check_intel.main(["node_label_is_attached"])
        mocked.assert_called_once_with(
            "kubectl",
            "get",
            "node",
            "-o",
            "jsonpath='{.items[0].metadata.labels.intel\\.feature\\.node\\.kubernetes\\.io/gpu}')",  # noqa: E501
        )
