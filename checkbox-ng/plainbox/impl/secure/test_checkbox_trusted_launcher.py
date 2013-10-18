# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.secure.test_checkbox_trusted_launcher
===================================================

Test definitions for plainbox.impl.secure.checkbox_trusted_launcher module
"""

from inspect import cleandoc
from io import StringIO
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import TestCase
import os

from plainbox.impl.secure.checkbox_trusted_launcher import Runner
from plainbox.impl.secure.checkbox_trusted_launcher import main
from plainbox.testing_utils.io import TestIO
from plainbox.vendor.mock import Mock, patch


class TestMain(TestCase):

    def setUp(self):
        self.scratch_dir = TemporaryDirectory(prefix='checkbox-')
        job_dir = os.path.join(self.scratch_dir.name, 'jobs')
        os.mkdir(job_dir)
        with NamedTemporaryFile(suffix='.txt', dir=job_dir, delete=False) as f:
            f.write(b'plugin: plugin\nuser: me\ncommand: true\n')
        with NamedTemporaryFile(
                suffix='.txt', dir=job_dir, delete=False) as f:
            f.write(b'plugin: unknown\nuser: user\n')
        with NamedTemporaryFile(
                suffix='.txt', dir=job_dir, delete=False) as f:
            f.write(b'plugin: local\nuser: you\ncommand: a new job\n')
        with NamedTemporaryFile(
                suffix='.conf', dir=job_dir, delete=False) as f:
            f.write(b'plugin: local\nuser: you\ncommand: a new job\n')

    def test_help(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--help'])
        self.assertEqual(call.exception.args, (0,))
        self.maxDiff = None
        expected = """
        usage: checkbox-trusted-launcher [-h] (--hash HASH | --warmup)
                                         [--via LOCAL-JOB-HASH]
                                         [NAME=VALUE [NAME=VALUE ...]]

        positional arguments:
          NAME=VALUE            Set each NAME to VALUE in the string environment

        optional arguments:
          -h, --help            show this help message and exit
          --hash HASH           job hash to match
          --warmup              Return immediately, only useful when used with
                                pkexec(1)
          --via LOCAL-JOB-HASH  Local job hash to use to match the generated job
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    def test_warmup(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--warmup'])
            self.assertEqual(call.exception.args, (0,))
        self.assertEqual(io.combined, '')

    def test_run_without_args(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main([])
            self.assertEqual(call.exception.args, (2,))
        expected = """
        usage: checkbox-trusted-launcher [-h] (--hash HASH | --warmup)
                                         [--via LOCAL-JOB-HASH]
                                         [NAME=VALUE [NAME=VALUE ...]]
        checkbox-trusted-launcher: error: one of the arguments --hash --warmup is required
        """
        self.assertEqual(io.combined, cleandoc(expected) + "\n")

    @patch.object(Runner, 'CHECKBOXES', 'foo')
    def test_run_invalid_hash(self):
        with TestIO(combined=True) as io:
            with self.assertRaises(SystemExit) as call:
                main(['--hash=bar'])
            self.assertEqual(call.exception.args, ('Job not found',))
        self.assertEqual(io.combined, '')

    def test_run_valid_hash(self):
        self.maxDiff = None
        with patch.object(Runner, 'CHECKBOXES', self.scratch_dir.name),\
                patch('os.execve'):
            with TestIO(combined=True) as io:
                with self.assertRaises(SystemExit) as call:
                    main(['--hash=9ab0e98cce8866b9a2fa217e87b4e8bb'
                          '739e5f74977ba5fa30822cab2a178c48'])
                self.assertEqual(call.exception.args, ('Fatal error',))
            self.assertEqual(io.combined, '')

    def test_run_valid_hash_exec_error(self):
        self.maxDiff = None
        with patch.object(Runner, 'CHECKBOXES', self.scratch_dir.name),\
                patch('os.execve') as mock_execve:
            mock_execve.side_effect = OSError('foo')
            with TestIO(combined=True) as io:
                with self.assertRaises(SystemExit) as call:
                    main(['--hash=9ab0e98cce8866b9a2fa217e87b4e8bb'
                          '739e5f74977ba5fa30822cab2a178c48'])
                self.assertEqual(call.exception.args, ('Fatal error',))
            self.assertEqual(io.combined, '')

    def test_run_valid_hash_invalid_via(self):
        self.maxDiff = None
        with patch.object(Runner, 'CHECKBOXES', self.scratch_dir.name),\
                patch('os.execve'),\
                patch('subprocess.Popen') as mock_popen:
            mock_iobuffer = Mock()
            mock_iobuffer.stdout = StringIO('test: me')
            mock_popen.return_value = mock_iobuffer
            with TestIO(combined=True) as io:
                with self.assertRaises(SystemExit) as call:
                    main(['--hash=9ab0e98cce8866b9a2fa217e87b4e8bb'
                          '739e5f74977ba5fa30822cab2a178c48', '--via=maybe'])
                self.assertEqual(call.exception.args, ('Fatal error',))
            self.assertEqual(io.combined, '')

    def test_run_valid_hash_valid_via(self):
        self.maxDiff = None
        with patch.object(Runner, 'CHECKBOXES', self.scratch_dir.name),\
                patch('os.execve'),\
                patch('subprocess.Popen') as mock_popen:
            mock_iobuffer = Mock()
            mock_iobuffer.stdout = StringIO('test: me')
            mock_popen.return_value = mock_iobuffer
            with TestIO(combined=True) as io:
                with self.assertRaises(SystemExit) as call:
                    main(['--hash=9ab0e98cce8866b9a2fa217e87b4e8bb'
                          '739e5f74977ba5fa30822cab2a178c48',
                          '--via=a0dc4a9673b8f2d80b1ae4775c'
                          '03e8a777eefa061fc7ecf7a3af2f20a33bb177'])
                self.assertEqual(call.exception.args, ('Fatal error',))
            self.assertEqual(io.combined, '')

    def tearDown(self):
        self.scratch_dir.cleanup()
