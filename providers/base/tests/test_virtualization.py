#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import itertools
from unittest import TestCase
from unittest.mock import patch, MagicMock

from virtualization import LXDTest_vm


class TestLXDTest_vm(TestCase):
    @patch("virtualization.logging")
    @patch("virtualization.RunCommand")
    def test_run_command_error(self, run_command_mock, logging_mock):
        task = run_command_mock()
        task.returncode = 1
        task.stdout = "abc"
        task.stderr = "some error"

        command_result = LXDTest_vm.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.error.called)
        self.assertFalse(command_result)

    @patch("virtualization.logging")
    @patch("virtualization.RunCommand")
    def test_run_command_ok(self, run_command_mock, logging_mock):
        task = run_command_mock()
        task.returncode = 0
        task.stdout = "abc"
        task.stderr = "some error"

        command_result = LXDTest_vm.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(command_result)

    @patch("virtualization.logging")
    def test_cleanup(self, logging_mock):
        self_mock = MagicMock()
        LXDTest_vm.cleanup(self_mock)

        self.assertTrue(self_mock.run_command.called)

    @patch("virtualization.logging")
    def test_start_vm_fail_setup(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = False

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertTrue(logging_mock.error.called)
        self.assertFalse(start_result)

    @patch("virtualization.logging")
    def test_start_vm_fail_init_no_img_alias(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = None
        self_mock.template_url = None
        self_mock.default_remote = "def remote"
        self_mock.os_version = "os version"
        self_mock.name = "name"
        self_mock.run_command.side_effect = [False]

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertFalse(start_result)

    @patch("virtualization.logging")
    def test_start_vm_fail_init_img_alias(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image url"
        self_mock.template_url = "template url"
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = [False]

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertFalse(start_result)

    @patch("virtualization.logging")
    def test_start_vm_fail_start(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image url"
        self_mock.template_url = "template url"
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = [True, False]

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertFalse(start_result)

    @patch("virtualization.logging")
    def test_start_vm_fail_list(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image url"
        self_mock.template_url = "template url"
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = [True, True, False]

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertFalse(start_result)

    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_start_vm_fail_exec(self, logging_mock, time_sleep_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image url"
        self_mock.template_url = "template url"
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = itertools.chain(
            [True, True, True], itertools.repeat(False)
        )

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertFalse(start_result)

    @patch("time.sleep")
    @patch("virtualization.print")
    @patch("virtualization.logging")
    def test_start_vm_success(self, logging_mock, print_mock, time_sleep_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image url"
        self_mock.template_url = "template url"
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = [True, True, True, True]

        start_result = LXDTest_vm.start_vm(self_mock)

        self.assertTrue(self_mock.setup.called)
        self.assertTrue(start_result)
        self.assertTrue(print_mock.called)

    def test_setup_failure(self):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False
        self_mock.template_url = None
        self_mock.image_url = None

        setup_return = LXDTest_vm.setup(self_mock)

        self.assertFalse(setup_return)
