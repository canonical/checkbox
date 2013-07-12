# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.test_runner
=========================

Test definitions for plainbox.impl.runner module
"""

from mock import Mock, patch
from tempfile import TemporaryDirectory
from unittest import TestCase
import os

from plainbox.impl.job import JobDefinition
from plainbox.impl.runner import CommandOutputWriter
from plainbox.impl.runner import FallbackCommandOutputPrinter
from plainbox.impl.runner import IOLogRecordGenerator
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import slugify
from plainbox.testing_utils.io import TestIO


class SlugifyTests(TestCase):

    def test_random_strings(self):
        self.assertEqual(slugify("A "), "A_")
        self.assertEqual(slugify("A-"), "A-")
        self.assertEqual(slugify("A_"), "A_")
        self.assertEqual(slugify(".b"), ".b")
        self.assertEqual(slugify("\z"), "_z")
        self.assertEqual(slugify("/z"), "_z")
        self.assertEqual(slugify("1k"), "1k")


class IOLogGeneratorTests(TestCase):

    def test_smoke(self):
        builder = IOLogRecordGenerator()
        # Calling on_begin() resets internal state
        builder.on_begin(None, None)
        builder.on_new_record.connect(
            lambda record: setattr(self, 'last_record', record))
        # Calling on_line generates records
        builder.on_line('stdout', b'text\n')
        self.assertEqual(self.last_record.stream_name, 'stdout')
        self.assertEqual(self.last_record.data, b'text\n')
        builder.on_line('stdout', b'different text\n')
        self.assertEqual(self.last_record.stream_name, 'stdout')
        self.assertEqual(self.last_record.data, b'different text\n')
        builder.on_line('stderr', b'error message\n')
        self.assertEqual(self.last_record.stream_name, 'stderr')
        self.assertEqual(self.last_record.data, b'error message\n')


class FallbackCommandOutputPrinterTests(TestCase):

    def test_smoke(self):
        with TestIO(combined=False) as io:
            obj = FallbackCommandOutputPrinter("example")
            # Whatever gets printed by the job...
            obj.on_line('stdout', b'line 1\n')
            obj.on_line('stderr', b'line 1\n')
            obj.on_line('stdout', b'line 2\n')
            obj.on_line('stdout', b'line 3\n')
            obj.on_line('stderr', b'line 2\n')
        # Gets printed to stdout _only_, stderr is combined with stdout here
        self.assertEqual(io.stdout, (
            "(job example, <stdout:00001>) line 1\n"
            "(job example, <stderr:00001>) line 1\n"
            "(job example, <stdout:00002>) line 2\n"
            "(job example, <stdout:00003>) line 3\n"
            "(job example, <stderr:00002>) line 2\n"
        ))


class CommandOutputWriterTests(TestCase):

    def assertFileContentsEqual(self, pathname, contents):
        with open(pathname, 'rb') as stream:
            self.assertEqual(stream.read(), contents)

    def test_smoke(self):
        with TemporaryDirectory() as scratch_dir:
            stdout = os.path.join(scratch_dir,  "stdout")
            stderr = os.path.join(scratch_dir,  "stderr")
            writer = CommandOutputWriter(stdout, stderr)
            # Initially nothing is created
            self.assertFalse(os.path.exists(stdout))
            self.assertFalse(os.path.exists(stderr))
            # Logs are created when the command is first started
            writer.on_begin(None, None)
            self.assertTrue(os.path.exists(stdout))
            self.assertTrue(os.path.exists(stderr))
            # Each line simply gets saved
            writer.on_line('stdout', b'text\n')
            writer.on_line('stderr', b'error\n')
            # (but it may not be on disk yet because of buffering)
            # After the command is done the logs are left on disk
            writer.on_end(None)
            self.assertFileContentsEqual(stdout, b'text\n')
            self.assertFileContentsEqual(stderr, b'error\n')


class GetScriptEnvTests(TestCase):

    def test_root_env_without_environ_keys(self):
        with patch.dict('os.environ', {'foo': 'bar'}):
            job = JobDefinition({
                'name': 'name',
                'plugin': 'plugin',
                'user': 'root',
            })
            job._provider = Mock()
            job._provider.extra_PYTHONPATH = None
            job._provider.extra_PATH = ""
            self.assertNotIn(
                "foo",
                JobRunner._get_script_env(Mock(), job, only_changes=True))

    def test_root_env_with_environ_keys(self):
        with patch.dict('os.environ', {'foo': 'bar'}):
            job = JobDefinition({
                'name': 'name',
                'plugin': 'plugin',
                'user': 'root',
                'environ': 'foo'
            })
            job._provider = Mock()
            job._provider.extra_PYTHONPATH = None
            job._provider.extra_PATH = ""
            self.assertIn(
                "foo",
                JobRunner._get_script_env(Mock(), job, only_changes=True))

    def test_user_env_without_environ_keys(self):
        with patch.dict('os.environ', {'foo': 'bar'}):
            job = JobDefinition({
                'name': 'name',
                'plugin': 'plugin',
            })
            job._provider = Mock()
            job._provider.extra_PYTHONPATH = None
            job._provider.extra_PATH = ""
            self.assertIn(
                "foo",
                JobRunner._get_script_env(Mock(), job, only_changes=False))

    def test_user_env_with_environ_keys(self):
        with patch.dict('os.environ', {'foo': 'bar'}):
            job = JobDefinition({
                'name': 'name',
                'plugin': 'plugin',
                'environ': 'foo'
            })
            job._provider = Mock()
            job._provider.extra_PYTHONPATH = None
            job._provider.extra_PATH = ""
            self.assertIn(
                "foo",
                JobRunner._get_script_env(Mock(), job, only_changes=False))
