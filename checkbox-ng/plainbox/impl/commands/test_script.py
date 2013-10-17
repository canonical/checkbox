# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.commands.test_script
==================================

Test definitions for plainbox.impl.script module
"""

import argparse
from inspect import cleandoc
from unittest import TestCase

from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.commands.script import ScriptInvocation, ScriptCommand
from plainbox.impl.providers.v1 import DummyProvider1
from plainbox.impl.testing_utils import make_job
from plainbox.testing_utils.io import TestIO
from plainbox.vendor import mock


class TestScriptCommand(TestCase):

    def setUp(self):
        self.parser = argparse.ArgumentParser(prog='test')
        self.subparsers = self.parser.add_subparsers()
        self.provider_list = [mock.Mock()]
        self.config = mock.Mock()
        self.ns = mock.Mock()

    def test_init(self):
        script_cmd = ScriptCommand(self.provider_list, self.config)
        self.assertIs(script_cmd.provider_list, self.provider_list)
        self.assertIs(script_cmd.config, self.config)

    def test_register_parser(self):
        ScriptCommand(self.provider_list, self.config).register_parser(
            self.subparsers)
        with TestIO() as io:
            self.parser.print_help()
        self.assertIn("script    run a command from a job", io.stdout)
        with TestIO() as io:
            with self.assertRaises(SystemExit):
                self.parser.parse_args(['script', '--help'])
        self.assertEqual(
            io.stdout, cleandoc(
                """
                usage: test script [-h] JOB-NAME

                positional arguments:
                  JOB-NAME    Name of the job to run

                optional arguments:
                  -h, --help  show this help message and exit
                """)
            + "\n")

    @mock.patch("plainbox.impl.commands.script.ScriptInvocation")
    def test_invoked(self, patched_ScriptInvocation):
        retval = ScriptCommand(self.provider_list, self.config).invoked(self.ns)
        patched_ScriptInvocation.assert_called_once_with(
            self.provider_list, self.config, self.ns.job_name)
        self.assertEqual(
            retval, patched_ScriptInvocation(
                self.provider_list, self.config,
                self.ns.job_name).run.return_value)


class ScriptInvocationTests(TestCase):

    def setUp(self):
        self.provider_list = mock.Mock()
        self.config = PlainBoxConfig()
        self.job_name = mock.Mock()

    def test_init(self):
        script_inv = ScriptInvocation(
            self.provider_list, self.config, self.job_name)
        self.assertIs(script_inv.provider_list, self.provider_list)
        self.assertIs(script_inv.config, self.config)
        self.assertIs(script_inv.job_name, self.job_name)

    def test_run_no_such_job(self):
        provider_list = [DummyProvider1()]
        script_inv = ScriptInvocation(provider_list, self.config, 'foo')
        with TestIO() as io:
            retval = script_inv.run()
        self.assertEqual(
            io.stdout, cleandoc(
                """
                There is no job called 'foo'
                See `plainbox special --list-jobs` for a list of choices
                """) + '\n')
        self.assertEqual(retval, 126)

    def test_run_job_without_command(self):
        provider_list = [DummyProvider1([make_job('foo')])]
        script_inv = ScriptInvocation(provider_list, self.config, 'foo')
        with TestIO() as io:
            retval = script_inv.run()
        self.assertEqual(
            io.stdout, cleandoc(
                """
                Selected job does not have a command
                """) + '\n')
        self.assertEqual(retval, 125)

    def test_job_with_command(self):
        dummy_name = 'foo'
        dummy_command = 'echo ok'
        provider_list = [DummyProvider1([
            make_job(dummy_name, command=dummy_command)])]
        script_inv = ScriptInvocation(provider_list, self.config, dummy_name)
        with TestIO() as io:
            retval = script_inv.run()
        self.assertEqual(
            io.stdout, cleandoc(
                """
                (job foo, <stdout:00001>) ok
                """) + '\n' + "{} returned 0\n".format(dummy_name) +
                "command: {}\n".format(dummy_command))
        self.assertEqual(retval, 0)

    def test_job_with_command_making_files(self):
        dummy_name = 'foo'
        dummy_command = 'echo ok > file'
        provider_list = [DummyProvider1([
            make_job(dummy_name, command=dummy_command)])]
        script_inv = ScriptInvocation(provider_list, self.config, dummy_name)
        with TestIO() as io:
            retval = script_inv.run()
        self.maxDiff = None
        self.assertEqual(
            io.stdout, cleandoc(
                """
                Leftover file detected: 'files-created-in-current-dir/file':
                  files-created-in-current-dir/file:1: ok
                """) + '\n' + "{} returned 0\n".format(dummy_name) +
                "command: {}\n".format(dummy_command))
        self.assertEqual(retval, 0)
