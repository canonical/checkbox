# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

"""
plainbox.impl.secure.test_launcher1
===================================

Test definitions for plainbox.impl.secure.launcher1 module
"""

from inspect import cleandoc
from unittest import TestCase
import os

from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.launcher1 import TrustedLauncher
from plainbox.impl.secure.launcher1 import main
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1PlugIn
from plainbox.impl.secure.providers.v1 import all_providers
from plainbox.impl.secure.providers.v1 import get_secure_PROVIDERPATH_list
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.testing_utils.io import TestIO
from plainbox.vendor import mock


class TrustedLauncherTests(TestCase):
    """
    Unit tests for the TrustedLauncher class that implements much of
    plainbox-trusted-launcher-1
    """

    def setUp(self):
        self.launcher = TrustedLauncher()

    def test_init(self):
        self.assertEqual(self.launcher._job_list, [])

    def test_add_job_list(self):
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        # Ensure that the job was added correctly
        self.assertEqual(self.launcher._job_list, [job])

    def test_find_job_when_it_doesnt_work(self):
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        with self.assertRaises(LookupError) as boom:
            self.launcher.find_job('foo')
        # Ensure that LookupError is raised if a job cannot be found
        self.assertIsInstance(boom.exception, LookupError)
        self.assertEqual(boom.exception.args, (
            'Cannot find job with checksum foo',))

    def test_find_job_when_it_works(self):
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        # Ensure that the job was found correctly
        self.assertIs(self.launcher.find_job(job.checksum), job)

    @mock.patch.dict('os.environ', clear=True)
    @mock.patch('subprocess.call')
    def test_run_shell_from_job(self, mock_call):
        # Create a mock job and add it to the launcher
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        # Create a environment we'll pass (empty)
        env = {'key': 'value'}
        # Run the tested method
        retval = self.launcher.run_shell_from_job(job.checksum, env)
        # Ensure that we run the job command via job.shell
        mock_call.assert_called_once_with(
            [job.shell, '-c', job.command], env=env)
        # Ensure that the return value of subprocess.call() is returned
        self.assertEqual(retval, mock_call())

    @mock.patch.dict('os.environ', clear=True, DISPLAY='foo')
    @mock.patch('subprocess.call')
    def test_run_shell_from_job_with_env_preserved(self, mock_call):
        # Create a mock job and add it to the launcher
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        # Create a environment we'll pass (empty)
        env = {'key': 'value'}
        # Run the tested method
        retval = self.launcher.run_shell_from_job(job.checksum, env)
        # Ensure that we run the job command via job.shell with a preserved env
        expected_env = dict(os.environ)
        expected_env.update(env)
        mock_call.assert_called_once_with(
            [job.shell, '-c', job.command], env=expected_env)
        # Ensure that the return value of subprocess.call() is returned
        self.assertEqual(retval, mock_call())

    @mock.patch.dict('os.environ', clear=True)
    @mock.patch('plainbox.impl.job.JobDefinition.from_rfc822_record')
    @mock.patch('plainbox.impl.secure.launcher1.load_rfc822_records')
    @mock.patch('subprocess.check_output')
    def test_run_local_job(self, mock_check_output, mock_load_rfc822_records,
                           mock_from_rfc822_record):
        # Create a mock job and add it to the launcher
        job = mock.Mock(spec=JobDefinition, name='job')
        self.launcher.add_job_list([job])
        # Create two mock rfc822 records
        record1 = mock.Mock(spec=RFC822Record, name='record')
        record2 = mock.Mock(spec=RFC822Record, name='record')
        # Ensure that load_rfc822_records() returns some mocked records
        mock_load_rfc822_records.return_value = [record1, record2]
        # Run the tested method
        job_list = self.launcher.run_local_job(job.checksum, None)
        # Ensure that we run the job command via job.shell
        mock_check_output.assert_called_with(
            [job.shell, '-c', job.command], env={}, universal_newlines=True)
        # Ensure that we parse all of the output
        mock_load_rfc822_records.assert_called_with(
            mock_check_output(), source=JobOutputTextSource(job))
        # Ensure that we return the jobs back
        self.assertEqual(len(job_list), 2)
        self.assertEqual(job_list[0], mock_from_rfc822_record(record1))
        self.assertEqual(job_list[1], mock_from_rfc822_record(record2))


class MainTests(TestCase):
    """
    Unit tests for the main() function that implements
    plainbox-trusted-launcher-1
    """

    def setUp(self):
        self.provider = mock.Mock(name='provider', spec=Provider1)
        all_providers.fake_plugins([
            mock.Mock(
                name='plugin',
                spec=Provider1PlugIn,
                plugin_name='{}/fake.provider'.format(
                    get_secure_PROVIDERPATH_list()[0]),
                plugin_object=self.provider)
        ])

    def test_help(self):
        """
        verify how `plainbox-trusted-launcher-1 --help` looks like
        """
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: plainbox-trusted-launcher-1 [-h] (-w | -t CHECKSUM)
                                           [-T NAME=VALUE [NAME=VALUE ...]]
                                           [-g CHECKSUM]
                                           [-G NAME=VALUE [NAME=VALUE ...]]

        optional arguments:
          -h, --help            show this help message and exit
          -w, --warmup          return immediately, only useful when used with
                                pkexec(1)
          -t CHECKSUM, --target CHECKSUM
                                run a job with this checksum

        target job specification:
          -T NAME=VALUE [NAME=VALUE ...], --target-environment NAME=VALUE [NAME=VALUE ...]
                                environment passed to the target job

        generator job specification:
          -g CHECKSUM, --generator CHECKSUM
                                also run a job with this checksum (assuming it is a
                                local job)
          -G NAME=VALUE [NAME=VALUE ...], --generator-environment NAME=VALUE [NAME=VALUE ...]
                                environment passed to the generator job
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_warmup(self):
        """
        verify what `plainbox-trusted-launcher-1 --warmup` does
        """
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            retval = main(['--warmup'])
        # Ensure that it just returns 0
        self.assertEqual(retval, 0)
        # Without printing anything
        self.assertEqual(io.combined, '')

    def test_run_without_args(self):
        """
        verify what `plainbox-trusted-launcher-1` does
        """
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main([])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: plainbox-trusted-launcher-1 [-h] (-w | -t CHECKSUM)
                                           [-T NAME=VALUE [NAME=VALUE ...]]
                                           [-g CHECKSUM]
                                           [-G NAME=VALUE [NAME=VALUE ...]]
        plainbox-trusted-launcher-1: error: one of the arguments -w/--warmup -t/--target is required
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    @mock.patch('plainbox.impl.secure.launcher1.TrustedLauncher')
    def test_run_valid_hash(self, mock_launcher):
        """
        verify what happens when `plainbox-trusted-launcher-1` is called with
        --hash that designates an existing job.
        """
        # Create a mock job, give it a predictable checksum
        job = mock.Mock(name='job', spec=JobDefinition, checksum='1234')
        # Ensure this job is enumerated by the provider
        self.provider.get_builtin_jobs.return_value = [job]
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            retval = main([
                '--target=1234', '-T', 'key=value', '-T', 'other=value'])
        # Ensure that the job command was invoked
        # and that environment was properly parsed and provided
        mock_launcher().run_shell_from_job.assert_called_with(
            job.checksum, {'key': 'value', 'other': 'value'})
        # Ensure that the return code is propagated
        self.assertEqual(retval, mock_launcher().run_shell_from_job())
        # Ensure that we didn't print anything (we normally do but this is not
        # tested here since we mock that part away)
        self.assertEqual(io.combined, '')

    @mock.patch('plainbox.impl.secure.launcher1.TrustedLauncher')
    def test_run_valid_hash_and_via(self, mock_launcher):
        """
        verify what happens when `plainbox-trusted-launcher-1` is called with
        both --hash and --via that both are okay and designate existing jobs.
        """
        # Create a mock (local) job, give it a predictable checksum
        local_job = mock.Mock(
            name='local_job',
            spec=JobDefinition,
            checksum='5678')
        # Create a mock (target) job, give it a predictable checksum
        target_job = mock.Mock(
            name='target_job',
            spec=JobDefinition,
            checksum='1234')
        # Ensure this local job is enumerated by the provider
        self.provider.get_builtin_jobs.return_value = [local_job]
        # Ensure that the target job is generated by the local job
        mock_launcher.run_local_job.return_value = [target_job]
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            retval = main(['--target=1234', '--generator=5678'])
        # Ensure that the local job command was invoked
        mock_launcher().run_local_job.assert_called_with(local_job.checksum, None)
        # Ensure that the target job command was invoked
        mock_launcher().run_shell_from_job.assert_called_with(
            target_job.checksum, None)
        # Ensure that the return code is propagated
        self.assertEqual(retval, mock_launcher().run_shell_from_job())
        # Ensure that we didn't print anything (we normally do but this is not
        # tested here since we mock that part away)
        self.assertEqual(io.combined, '')

    def test_run_invalid_target_checksum(self):
        """
        verify what happens when `plainbox-trusted-launcher-1` is called with a
        target job checksum that cannot be found in any of the providers.
        """
        # Ensure this there are no jobs that the launcher knows about
        self.provider.get_builtin_jobs.return_value = []
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--target=1234'])
        # Ensure that the error message contains the checksum of the target job
        self.assertEqual(call.exception.args, (
            'Cannot find job with checksum 1234',))
        self.assertEqual(io.combined, '')

    def test_run_invalid_generator_checksum(self):
        """
        verify what happens when `plainbox-trusted-launcher-1` is called with a
        generator job checksum that cannot be found in any of the providers.
        """
        # Ensure this there are no jobs that the launcher knows about
        self.provider.get_builtin_jobs.return_value = []
        # Run the program with io intercept
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--target=1234', '--generator=4567'])
        # Ensure that the error message contains the checksum of the via job
        self.assertEqual(call.exception.args, (
            'Cannot find job with checksum 4567',))
        # Ensure that we didn't print anything (we normally do but this is not
        # tested here since we mock that part away)
        self.assertEqual(io.combined, '')

    def test_run_invalid_env(self):
        """
        verify what happens when `plainbox-trusted-launcher-1` is called with a
        checksum that cannot be found in any of the providers.
        """
       # Run the program with io intercept
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--target=1234', '-T', 'blarg'])
        # Ensure that we exit with an error code
        self.assertEqual(call.exception.args, (2,))
        # Ensure that we print a meaningful error message
        expected = """
        usage: plainbox-trusted-launcher-1 [-h] (-w | -t CHECKSUM)
                                           [-T NAME=VALUE [NAME=VALUE ...]]
                                           [-g CHECKSUM]
                                           [-G NAME=VALUE [NAME=VALUE ...]]
        plainbox-trusted-launcher-1: error: argument -T/--target-environment: expected NAME=VALUE
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")
