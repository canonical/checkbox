# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
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
:mod:`plainbox.impl.session.test_suspend`
=========================================

Test definitions for :mod:`plainbox.impl.session.suspend` module
"""

from functools import partial
from unittest import TestCase
import gzip

from plainbox.abc import IJobResult
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.suspend import SessionSuspendHelper1
from plainbox.impl.session.suspend import SessionSuspendHelper2
from plainbox.impl.session.suspend import SessionSuspendHelper3
from plainbox.impl.session.suspend import SessionSuspendHelper4
from plainbox.impl.session.suspend import SessionSuspendHelper5
from plainbox.impl.session.suspend import SessionSuspendHelper6
from plainbox.impl.testing_utils import make_job
from plainbox.vendor import mock


class BaseJobResultTestsTestsMixIn:
    """
    Mix-in that tests a number of shared aspects of DiskJobResult
    and MemoryJobResult. To use sub-class this mix-in with TestCase
    and set ``repr_method`` and ``TESTED_CLS`` to something sensible.

    :cvar:`repr_method`` should be one of
    :meth:`plainbox.impl.session.suspend.SessionSuspendHelper.
    _repr_DiskJobResult()`, :meth:`plainbox.impl.session.suspend.
    SessionSuspendHelper._repr_MemoryJobResult()`.

    :cvar:`TESTED_CLS` should be one of
    :class:`plainbox.impl.result.MemoryJobResult`
    or :class:`plainbox.impl.result.DiskJobResult`
    """

    def setUp(self):
        self.helper = self.HELPER_CLS()
        self.empty_result = self.TESTED_CLS({})
        self.typical_result = self.TESTED_CLS({
            "outcome": self.TESTED_CLS.OUTCOME_PASS,
            "execution_duration": 42.5,
            "comments": "the screen was corrupted",
            "return_code": 1,
            # NOTE: those are actually specific to TESTED_CLS but it is
            # a simple hack that gets the job done
            "io_log_filename": "/path/to/log.txt",
            "io_log": [
                (0, 'stdout', b'first part\n'),
                (0.1, 'stdout', b'second part\n'),
            ]
        })
        self.session_dir = None

    def test_repr_xxxJobResult_outcome(self):
        """
        verify that DiskJobResult.outcome is serialized correctly
        """
        data = self.repr_method(self.typical_result, self.session_dir)
        self.assertEqual(data['outcome'], DiskJobResult.OUTCOME_PASS)

    def test_repr_xxxJobResult_execution_duration(self):
        """
        verify that DiskJobResult.execution_duration is serialized correctly
        """
        data = self.repr_method(self.typical_result, self.session_dir)
        self.assertAlmostEqual(data['execution_duration'], 42.5)

    def test_repr_xxxJobResult_comments(self):
        """
        verify that DiskJobResult.comments is serialized correctly
        """
        data = self.repr_method(self.typical_result, self.session_dir)
        self.assertEqual(data['comments'], "the screen was corrupted")

    def test_repr_xxxJobResult_return_code(self):
        """
        verify that DiskJobResult.return_code is serialized correctly
        """
        data = self.repr_method(self.typical_result, self.session_dir)
        self.assertEqual(data['return_code'], 1)


class SuspendMemoryJobResultTests(BaseJobResultTestsTestsMixIn, TestCase):
    """
    Tests that check how MemoryJobResult is represented by SessionSuspendHelper
    """

    TESTED_CLS = MemoryJobResult
    HELPER_CLS = SessionSuspendHelper1

    def setUp(self):
        super(SuspendMemoryJobResultTests, self).setUp()
        self.repr_method = self.helper._repr_MemoryJobResult

    def test_repr_MemoryJobResult_empty(self):
        """
        verify that the representation of an empty MemoryJobResult is okay
        """
        data = self.repr_method(self.empty_result, self.session_dir)
        self.assertEqual(data, {
            "outcome": None,
            "execution_duration": None,
            "comments": None,
            "return_code": None,
            "io_log": [],
        })

    def test_repr_MemoryJobResult_io_log(self):
        """
        verify that MemoryJobResult.io_log is serialized correctly
        """
        data = self.helper._repr_MemoryJobResult(
            self.typical_result, self.session_dir)
        self.assertEqual(data['io_log'], [
            [0, 'stdout', 'Zmlyc3QgcGFydAo='],
            [0.1, 'stdout', 'c2Vjb25kIHBhcnQK'],
        ])


class SuspendDiskJobResultTests(BaseJobResultTestsTestsMixIn, TestCase):
    """
    Tests that check how DiskJobResult is represented by SessionSuspendHelper
    """

    TESTED_CLS = DiskJobResult
    HELPER_CLS = SessionSuspendHelper1

    def setUp(self):
        super(SuspendDiskJobResultTests, self).setUp()
        self.repr_method = self.helper._repr_DiskJobResult

    def test_repr_DiskJobResult_empty(self):
        """
        verify that the representation of an empty DiskJobResult is okay
        """
        data = self.repr_method(self.empty_result, self.session_dir)
        self.assertEqual(data, {
            "outcome": None,
            "execution_duration": None,
            "comments": None,
            "return_code": None,
            "io_log_filename": None,
        })

    def test_repr_DiskJobResult_io_log_filename(self):
        """
        verify that DiskJobResult.io_log_filename is serialized correctly
        """
        data = self.helper._repr_DiskJobResult(
            self.typical_result, self.session_dir)
        self.assertEqual(data['io_log_filename'], "/path/to/log.txt")


class Suspend5DiskJobResultTests(SuspendDiskJobResultTests):
    """
    Tests that check how DiskJobResult is represented by SessionSuspendHelper5
    """

    TESTED_CLS = DiskJobResult
    HELPER_CLS = SessionSuspendHelper5

    def test_repr_DiskJobResult_io_log_filename__no_session_dir(self):
        """ io_log_filename is absolute in session_dir is not used.  """
        data = self.helper._repr_DiskJobResult(
            self.typical_result, None)
        self.assertEqual(data['io_log_filename'], "/path/to/log.txt")

    def test_repr_DiskJobResult_io_log_filename__session_dir(self):
        """ io_log_filename is relative if session_dir is used. """
        data = self.helper._repr_DiskJobResult(
            self.typical_result, "/path/to")
        self.assertEqual(data['io_log_filename'], "log.txt")


class SessionSuspendHelper1Tests(TestCase):
    """
    Tests for various methods of SessionSuspendHelper
    """

    def setUp(self):
        self.helper = SessionSuspendHelper1()
        self.session_dir = None

    def test_repr_IOLogRecord(self):
        """
        verify that the representation of IOLogRecord is okay
        """
        record = IOLogRecord(0.0, "stdout", b"binary data")
        data = self.helper._repr_IOLogRecord(record)
        self.assertEqual(data, [0.0, "stdout", "YmluYXJ5IGRhdGE="])

    def test_repr_JobResult_with_MemoryJobResult(self):
        """
        verify that _repr_JobResult() called with MemoryJobResult
        calls _repr_MemoryJobResult
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_repr_MemoryJobResult'):
            result = MemoryJobResult({})
            self.helper._repr_JobResult(result, self.session_dir)
            self.helper._repr_MemoryJobResult.assert_called_once_with(
                result, None)

    def test_repr_JobResult_with_DiskJobResult(self):
        """
        verify that _repr_JobResult() called with DiskJobResult
        calls _repr_DiskJobResult
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_repr_DiskJobResult'):
            result = DiskJobResult({})
            self.helper._repr_JobResult(result, self.session_dir)
            self.helper._repr_DiskJobResult.assert_called_once_with(
                result, None)

    def test_repr_JobResult_with_junk(self):
        """
        verify that _repr_JobResult() raises TypeError when
        called with something other than JobResult instances
        """
        with self.assertRaises(TypeError):
            self.helper._repr_JobResult(None)

    def test_repr_SessionMetaData_empty_metadata(self):
        """
        verify that representation of empty SessionMetaData is okay
        """
        # all defaults with empty values
        data = self.helper._repr_SessionMetaData(
            SessionMetaData(), self.session_dir)
        self.assertEqual(data, {
            'title': None,
            'flags': [],
            'running_job_name': None
        })

    def test_repr_SessionMetaData_typical_metadata(self):
        """
        verify that representation of typical SessionMetaData is okay
        """
        # no surprises here, just the same data copied over
        data = self.helper._repr_SessionMetaData(SessionMetaData(
            title='USB Testing session',
            flags=['incomplete'],
            running_job_name='usb/detect'
        ), self.session_dir)
        self.assertEqual(data, {
            'title': 'USB Testing session',
            'flags': ['incomplete'],
            'running_job_name': 'usb/detect',
        })

    def test_repr_SessionState_empty_session(self):
        """
        verify that representation of empty SessionState is okay
        """
        data = self.helper._repr_SessionState(
            SessionState([]), self.session_dir)
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
            },
        })

    def test_json_repr_has_version_field(self):
        """
        verify that the json representation has the 'version' field
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertIn("version", data)

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 1)

    def test_json_repr_stores_session_state(self):
        """
        verify that the json representation has the 'session' field
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertIn("session", data)

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"flags":[],"running_job_name":null,"title":null},"results":{}'
            b'},"version":1}'))


class SessionSuspendHelper2Tests(SessionSuspendHelper1Tests):
    """
    Tests for various methods of SessionSuspendHelper2
    """

    def setUp(self):
        self.helper = SessionSuspendHelper2()
        self.session_dir = None

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 2)

    def test_repr_SessionMetaData_empty_metadata(self):
        """
        verify that representation of empty SessionMetaData is okay
        """
        # all defaults with empty values
        data = self.helper._repr_SessionMetaData(
            SessionMetaData(), self.session_dir)
        self.assertEqual(data, {
            'title': None,
            'flags': [],
            'running_job_name': None,
            'app_blob': None
        })

    def test_repr_SessionMetaData_typical_metadata(self):
        """
        verify that representation of typical SessionMetaData is okay
        """
        # no surprises here, just the same data copied over
        data = self.helper._repr_SessionMetaData(SessionMetaData(
            title='USB Testing session',
            flags=['incomplete'],
            running_job_name='usb/detect',
            app_blob=b'blob',
        ), self.session_dir)
        self.assertEqual(data, {
            'title': 'USB Testing session',
            'flags': ['incomplete'],
            'running_job_name': 'usb/detect',
            'app_blob': 'YmxvYg==',
        })

    def test_repr_SessionState_empty_session(self):
        """
        verify that representation of empty SessionState is okay
        """
        data = self.helper._repr_SessionState(
            SessionState([]), self.session_dir)
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
                'app_blob': None,
            },
        })

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(
            SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"app_blob":null,"flags":[],"running_job_name":null,"title":null'
            b'},"results":{}},"version":2}'))


class SessionSuspendHelper3Tests(SessionSuspendHelper2Tests):
    """
    Tests for various methods of SessionSuspendHelper3
    """

    def setUp(self):
        self.helper = SessionSuspendHelper3()
        self.session_dir = None

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 3)

    def test_repr_SessionMetaData_empty_metadata(self):
        """
        verify that representation of empty SessionMetaData is okay
        """
        # all defaults with empty values
        data = self.helper._repr_SessionMetaData(
            SessionMetaData(), self.session_dir)
        self.assertEqual(data, {
            'title': None,
            'flags': [],
            'running_job_name': None,
            'app_blob': None,
            'app_id': None
        })

    def test_repr_SessionMetaData_typical_metadata(self):
        """
        verify that representation of typical SessionMetaData is okay
        """
        # no surprises here, just the same data copied over
        data = self.helper._repr_SessionMetaData(SessionMetaData(
            title='USB Testing session',
            flags=['incomplete'],
            running_job_name='usb/detect',
            app_blob=b'blob',
            app_id='com.canonical.certification.plainbox',
        ), self.session_dir)
        self.assertEqual(data, {
            'title': 'USB Testing session',
            'flags': ['incomplete'],
            'running_job_name': 'usb/detect',
            'app_blob': 'YmxvYg==',
            'app_id': 'com.canonical.certification.plainbox'
        })

    def test_repr_SessionState_empty_session(self):
        """
        verify that representation of empty SessionState is okay
        """
        data = self.helper._repr_SessionState(
            SessionState([]), self.session_dir)
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
                'app_blob': None,
                'app_id': None,
            },
        })

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"app_blob":null,"app_id":null,"flags":[],'
            b'"running_job_name":null,"title":null},"results":{}},'
            b'"version":3}'))


class SessionSuspendHelper4Tests(SessionSuspendHelper3Tests):
    """
    Tests for various methods of SessionSuspendHelper4
    """

    def setUp(self):
        self.helper = SessionSuspendHelper4()
        self.session_dir = None

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 4)

    def test_repr_SessionState_typical_session(self):
        """
        verify the representation of a SessionState with some unused jobs

        Unused jobs should just have no representation. Their checksum
        should not be mentioned. Their results (empty results) should be
        ignored.
        """
        used_job = JobDefinition({
            "plugin": "shell",
            "id": "used",
            "command": "echo 'hello world'",
        })
        unused_job = JobDefinition({
            "plugin": "shell",
            "id": "unused",
            "command": "echo 'hello world'",
        })
        used_result = MemoryJobResult({
            "io_log": [
                (0.0, "stdout", b'hello world\n'),
            ],
            'outcome': IJobResult.OUTCOME_PASS
        })
        session_state = SessionState([used_job, unused_job])
        session_state.update_desired_job_list([used_job])
        session_state.update_job_result(used_job, used_result)
        data = self.helper._repr_SessionState(session_state, self.session_dir)
        self.assertEqual(data, {
            'jobs': {
                'used': ('8c393c19fdfde1b6afc5b79d0a1617ecf7531cd832a16450dc'
                         '2f3f50d329d373')
            },
            'results': {
                'used': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [[0.0, 'stdout', 'aGVsbG8gd29ybGQK']],
                    'outcome': 'pass',
                    'return_code': None
                }]
            },
            'desired_job_list': ['used'],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
                'app_blob': None,
                'app_id': None,
            },
        })

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"app_blob":null,"app_id":null,"flags":[],'
            b'"running_job_name":null,"title":null},"results":{}},'
            b'"version":4}'))


class SessionSuspendHelper5Tests(SessionSuspendHelper4Tests):
    """
    Tests for various methods of SessionSuspendHelper5
    """

    def setUp(self):
        self.helper = SessionSuspendHelper5()
        self.session_dir = None

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 5)

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"app_blob":null,"app_id":null,"flags":[],'
            b'"running_job_name":null,"title":null},"results":{}},'
            b'"version":5}'))


class SessionSuspendHelper6Tests(SessionSuspendHelper5Tests):
    """
    Tests for various methods of SessionSuspendHelper6
    """

    def setUp(self):
        self.helper = SessionSuspendHelper6()
        self.session_dir = None

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]), self.session_dir)
        self.assertEqual(data['version'], 6)

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]), self.session_dir)
        # XXX: we cannot really test what the compressed data looks like
        # because apparently python3.2 gzip output is non-deterministic.
        # It seems to be an instance of the gzip bug that was fixed a few
        # years ago.
        #
        # I've filed a bug on python3.2 in Ubuntu and Python upstream project
        # https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/871083
        #
        # In the meantime we can only test that we got bytes out
        self.assertIsInstance(data, bytes)
        # And that we can gzip uncompress them and get what we expected
        self.assertEqual(gzip.decompress(data), (
            b'{"session":{"desired_job_list":[],"jobs":{},'
            b'"mandatory_job_list":[],"metadata":'
            b'{"app_blob":null,"app_id":null,"flags":[],'
            b'"running_job_name":null,"title":null},"results":{}},'
            b'"version":6}'))

    def test_repr_SessionState_typical_session(self):
        """
        verify the representation of a SessionState with some unused jobs

        Unused jobs should just have no representation. Their checksum
        should not be mentioned. Their results (empty results) should be
        ignored.
        """
        used_job = JobDefinition({
            "plugin": "shell",
            "id": "used",
            "command": "echo 'hello world'",
        })
        unused_job = JobDefinition({
            "plugin": "shell",
            "id": "unused",
            "command": "echo 'hello world'",
        })
        used_result = MemoryJobResult({
            "io_log": [
                (0.0, "stdout", b'hello world\n'),
            ],
            'outcome': IJobResult.OUTCOME_PASS
        })
        session_state = SessionState([used_job, unused_job])
        session_state.update_desired_job_list([used_job])
        session_state.update_job_result(used_job, used_result)
        data = self.helper._repr_SessionState(session_state, self.session_dir)
        self.assertEqual(data, {
            'jobs': {
                'used': ('8c393c19fdfde1b6afc5b79d0a1617ecf7531cd832a16450dc'
                         '2f3f50d329d373')
            },
            'results': {
                'used': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [[0.0, 'stdout', 'aGVsbG8gd29ybGQK']],
                    'outcome': 'pass',
                    'return_code': None
                }]
            },
            'desired_job_list': ['used'],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
                'app_blob': None,
                'app_id': None,
            },
        })

    def test_repr_SessionState_empty_session(self):
        """
        verify that representation of empty SessionState is okay
        """
        data = self.helper._repr_SessionState(
            SessionState([]), self.session_dir)
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
            'mandatory_job_list': [],
            'metadata': {
                'title': None,
                'flags': [],
                'running_job_name': None,
                'app_blob': None,
                'app_id': None,
            },
        })


class RegressionTests(TestCase):

    def test_1388055(self):
        """
        https://bugs.launchpad.net/plainbox/+bug/1388055
        """
        # This bug is about being able to resume a session despite job database
        # modification. Let's assume the following session first:
        # - desired job list: [a]
        # - run list [a_dep, a] (computed)
        # - job_repr: {a_dep: checksum}
        job_a = make_job(id='a', depends='a_dep')
        job_a_dep = make_job(id='a_dep')
        state = SessionState([job_a, job_a_dep])
        state.update_desired_job_list([job_a])
        self.assertEqual(state.run_list, [job_a_dep, job_a])
        self.assertEqual(state.desired_job_list, [job_a])
        helper = SessionSuspendHelper4()
        session_dir = None
        # Mock away the meta-data as we're not testing that
        with mock.patch.object(helper, '_repr_SessionMetaData') as m:
            m.return_value = 'mocked'
            actual = helper._repr_SessionState(state, session_dir)
        expected = {
            'jobs': {
                job_a_dep.id: job_a_dep.checksum,
                job_a.id: job_a.checksum,
            },
            'desired_job_list': [job_a.id],
            'mandatory_job_list': [],
            'results': {},
            'metadata': 'mocked'
        }
        self.assertEqual(expected, actual)
