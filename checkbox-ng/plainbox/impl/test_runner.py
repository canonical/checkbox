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
plainbox.impl.test_runner
=========================

Test definitions for plainbox.impl.runner module
"""

from tempfile import TemporaryDirectory
from unittest import TestCase
import os

from plainbox.abc import IExecutionController
from plainbox.abc import IJobDefinition
from plainbox.impl.runner import CommandOutputWriter
from plainbox.impl.runner import FallbackCommandOutputPrinter
from plainbox.impl.runner import IOLogRecordGenerator
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import slugify
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import Mock


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


class RunnerTests(TestCase):

    def test_get_warm_up_sequence(self):
        # create a mocked execution controller
        ctrl = Mock(spec_set=IExecutionController, name='ctrl')
        # create a fake warm up function
        warm_up_func = Mock(name='warm_up_func')
        # make the execution controller accept any job
        ctrl.get_score.return_value = 1
        # make the execution controller return warm_up_func as warm-up
        ctrl.get_warm_up_for_job.return_value = warm_up_func
        # make a pair of mock jobs for our controller to see
        job1 = Mock(spec_set=IJobDefinition, name='job1')
        job2 = Mock(spec_set=IJobDefinition, name='job2')
        with TemporaryDirectory() as session_dir:
            # Create a real runner with a fake execution controller, empty list
            # of providers and fake io-log directory.
            runner = JobRunner(
                session_dir, provider_list=[],
                jobs_io_log_dir=os.path.join(session_dir, 'io-log'),
                execution_ctrl_list=[ctrl])
            # Ensure that we got the warm up function we expected
            self.assertEqual(
                runner.get_warm_up_sequence([job1, job2]), [warm_up_func])
