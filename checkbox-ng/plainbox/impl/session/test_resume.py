# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.session.test_resume`
========================================

Test definitions for :mod:`plainbox.impl.session.resume` module
"""

from unittest import TestCase
import base64
import binascii
import copy
import gzip
import json

import mock

from plainbox.impl.job import JobDefinition
from plainbox.impl.resource import Resource
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.resume import CorruptedSessionError
from plainbox.impl.session.resume import IncompatibleJobError
from plainbox.impl.session.resume import IncompatibleSessionError
from plainbox.impl.session.resume import SessionResumeError
from plainbox.impl.session.resume import SessionResumeHelper
from plainbox.impl.session.resume import SessionResumeHelper1
from plainbox.impl.session.resume import SessionResumeHelper2
from plainbox.impl.session.state import SessionState
from plainbox.impl.testing_utils import make_job
from plainbox.testing_utils.testcases import TestCaseWithParameters


class SessionResumeExceptionTests(TestCase):

    """
    Tests for the various exceptions defined in the resume module
    """

    def test_resume_exception_inheritance(self):
        """
        verify that all three exception classes inherit from the common base
        """
        self.assertTrue(issubclass(
            CorruptedSessionError, SessionResumeError))
        self.assertTrue(issubclass(
            IncompatibleSessionError, SessionResumeError))
        self.assertTrue(issubclass(
            IncompatibleJobError, SessionResumeError))


class SessionResumeHelperTests(TestCase):

    @mock.patch('plainbox.impl.session.resume.SessionResumeHelper1')
    def test_resume_dispatch_v1(self, mocked_helper1):
        data = gzip.compress(
            b'{"session":{"desired_job_list":[],"jobs":{},"metadata":'
            b'{"app_blob":null,"flags":[],"running_job_name":null,"title":null'
            b'},"results":{}},"version":1}')
        SessionResumeHelper([]).resume(data)
        mocked_helper1.resume_json.assertCalledOnce()

    @mock.patch('plainbox.impl.session.resume.SessionResumeHelper2')
    def test_resume_dispatch_v2(self, mocked_helper2):
        data = gzip.compress(
            b'{"session":{"desired_job_list":[],"jobs":{},"metadata":'
            b'{"app_blob":null,"flags":[],"running_job_name":null,"title":null'
            b'},"results":{}},"version":2}')
        SessionResumeHelper([]).resume(data)
        mocked_helper2.resume_json.assertCalledOnce()

    def test_resume_dispatch_v3(self):
        data = gzip.compress(
            b'{"version":3}')
        with self.assertRaises(IncompatibleSessionError) as boom:
            SessionResumeHelper([]).resume(data)
        self.assertEqual(str(boom.exception), "Unsupported version 3")


class SessionResumeTests(TestCase):

    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper`
    """

    def test_resume_garbage_gzip(self):
        """
        verify that CorruptedSessionError raised when we try to decompress
        garbage bytes. By "garbage" we mean that it's not a valid
        gzip-compressed stream. Internally IOError is raised but we wrap
        that for simplicity.
        """
        data = b"foo"
        with self.assertRaises(CorruptedSessionError) as boom:
            SessionResumeHelper([]).resume(data)
        self.assertIsInstance(boom.exception.__context__, IOError)

    def test_resume_garbage_unicode(self):
        """
        verify that CorruptedSessionError is raised when we try to interpret
        incorrect bytes as UTF-8. Internally UnicodeDecodeError is raised
        but we wrap that for simplicity.
        """
        # This is just a sanity check that b"\xff" is not a valid UTF-8 string
        with self.assertRaises(UnicodeDecodeError):
            b"\xff".decode('UTF-8')
        data = gzip.compress(b"\xff")
        with self.assertRaises(CorruptedSessionError) as boom:
            SessionResumeHelper([]).resume(data)
        self.assertIsInstance(boom.exception.__context__, UnicodeDecodeError)

    def test_resume_garbage_json(self):
        """
        verify that CorruptedSessionError is raised when we try to interpret
        malformed JSON text. Internally ValueError is raised but we wrap that
        for simplicity.
        """
        data = gzip.compress(b"{")
        with self.assertRaises(CorruptedSessionError) as boom:
            SessionResumeHelper([]).resume(data)
        self.assertIsInstance(boom.exception.__context__, ValueError)


class EndToEndTests(TestCaseWithParameters):

    parameter_names = ('format',)
    parameter_values = (('1',), ('2'),)

    full_repr_1 = {
        'version': 1,
        'session': {
            'jobs': {
                '__category__': (
                    '5267192a5eac9288d144242d800b981eeca476c17e0'
                    'dd32a09c4b3ea0a14f955'),
                'generator': (
                    '7e67e23b7e7a6a5803721a9f282c0e88c7f40bae470'
                    '950f880e419bb9c7665d8'),
                'generated': (
                    'bfee8c57b6adc9f0f281b59fe818de2ed98b6affb78'
                    '9cf4fbf282d89453190d3'),
            },
            'results': {
                '__category__': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [
                        [0.0, 'stdout', 'cGx1Z2luOmxvY2FsCg=='],
                        [0.1, 'stdout', 'bmFtZTpnZW5lcmF0b3IK']],
                    'outcome': None,
                    'return_code': None,
                }],
                'generator': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [
                        [0.0, 'stdout', 'bmFtZTpnZW5lcmF0ZWQ=']],
                    'outcome': None,
                    'return_code': None,
                }],
                'generated': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [],
                    'outcome': None,
                    'return_code': None,
                }]
            },
            'desired_job_list': ['__category__', 'generator'],
            'metadata': {
                'flags': [],
                'running_job_name': None,
                'title': None
            },
        }
    }

    # Copy and patch the v1 representation to get a v2 representation
    full_repr_2 = copy.deepcopy(full_repr_1)
    full_repr_2['version'] = 2
    full_repr_2['session']['metadata']['app_blob'] = None

    # Map of representation names to representations
    full_repr = {
        '1': full_repr_1,
        '2': full_repr_2
    }

    def setUp(self):
        # Crete a "__category__" job
        self.category_job = JobDefinition({
            "plugin": "local",
            "name": "__category__"
        })
        # Create a "generator" job
        self.generator_job = JobDefinition({
            "plugin": "local",
            "name": "generator"
        })
        # Keep a variable for the (future) generated job
        self.generated_job = None
        # Create a result for the "__category__" job.
        # It must define a verbatim copy of the "generator" job
        self.category_result = MemoryJobResult({
            "io_log": [
                (0.0, "stdout", b'plugin:local\n'),
                (0.1, "stdout", b'name:generator\n'),
            ]
        })
        # Create a result for the "generator" job.
        # It will define the "generated" job
        self.generator_result = MemoryJobResult({
            "io_log": [(0.0, 'stdout', b'name:generated')]
        })
        self.job_list = [self.category_job, self.generator_job]
        self.suspend_data = gzip.compress(
            json.dumps(self.full_repr[self.parameters.format]).encode("UTF-8"))

    def test_resume_early_callback(self):
        """
        verify that early_cb is called with a session object
        """
        def early_cb(session):
            self.seen_session = session
        session = SessionResumeHelper(self.job_list).resume(
            self.suspend_data, early_cb)
        self.assertIs(session, self.seen_session)


class IOLogRecordResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and how they
    handle resuming IOLogRecord objects
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,))

    def test_build_IOLogRecord_missing_delay(self):
        """
        verify that _build_IOLogRecord() checks for missing ``delay``
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([])

    def test_build_IOLogRecord_bad_type_for_delay(self):
        """
        verify that _build_IOLogRecord() checks that ``delay`` is float
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([0, 'stdout', ''])

    def test_build_IOLogRecord_negative_delay(self):
        """
        verify that _build_IOLogRecord() checks for negative ``delay``
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([-1.0, 'stdout', ''])

    def test_build_IOLogRecord_missing_stream_name(self):
        """
        verify that _build_IOLogRecord() checks for missing ``stream-name``
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([0.0])

    def test_build_IOLogRecord_bad_type_stream_name(self):
        """
        verify that _build_IOLogRecord() checks that ``stream-name``
        is a string
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([0.0, 1])

    def test_build_IOLogRecord_bad_value_stream_name(self):
        """
        verify that _build_IOLogRecord() checks that ``stream-name`` looks sane
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([0.0, "foo", ""])

    def test_build_IOLogRecord_missing_data(self):
        """
        verify that _build_IOLogRecord() checks for missing ``data``
        """
        with self.assertRaises(CorruptedSessionError):
            self.parameters.resume_cls._build_IOLogRecord([0.0, 'stdout'])

    def test_build_IOLogRecord_non_ascii_data(self):
        """
        verify that _build_IOLogRecord() checks that ``data`` is ASCII
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.parameters.resume_cls._build_IOLogRecord(
                [0.0, 'stdout', '\uFFFD'])
        self.assertIsInstance(boom.exception.__context__, UnicodeEncodeError)

    def test_build_IOLogRecord_non_base64_ascii_data(self):
        """
        verify that _build_IOLogRecord() checks that ``data`` is valid base64
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.parameters.resume_cls._build_IOLogRecord(
                [0.0, 'stdout', '==broken'])
        # base64.standard_b64decode() raises binascii.Error
        self.assertIsInstance(boom.exception.__context__, binascii.Error)

    def test_build_IOLogRecord_values(self):
        """
        verify that _build_IOLogRecord() returns a proper IOLogRecord object
        with all the values in order
        """
        record = self.parameters.resume_cls._build_IOLogRecord(
            [1.5, 'stderr', 'dGhpcyB3b3Jrcw=='])
        self.assertAlmostEqual(record.delay, 1.5)
        self.assertEqual(record.stream_name, 'stderr')
        self.assertEqual(record.data, b"this works")


class JobResultResumeMixIn:
    """
    Mix-in class the defines most of the common tests for both
    MemoryJobResult and DiskJobResult.

    Sub-classes should define ``good_repr`` at class level
    """

    good_repr = None

    def test_build_JobResult_checks_for_missing_outcome(self):
        """
        verify that _build_JobResult() checks if ``outcome`` is present
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['outcome']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), "Missing value for key 'outcome'")

    def test_build_JobResult_checks_type_of_outcome(self):
        """
        verify that _build_JobResult() checks if ``outcome`` is a string
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['outcome'] = 42
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'outcome' is of incorrect type int")

    def test_build_JobResult_checks_value_of_outcome(self):
        """
        verify that _build_JobResult() checks if the value of ``outcome`` is
        in the set of known-good values.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['outcome'] = 'maybe'
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), (
                "Value for key 'outcome' not in allowed set [None, 'pass', "
                "'fail', 'skip', 'not-supported', 'not-implemented', "
                "'undecided']"))

    def test_build_JobResult_allows_none_outcome(self):
        """
        verify that _build_JobResult() allows for the value of ``outcome`` to
        be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['outcome'] = None
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.outcome, None)

    def test_build_JobResult_restores_outcome(self):
        """
        verify that _build_JobResult() restores the value of ``outcome``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['outcome'] = 'fail'
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.outcome, 'fail')

    def test_build_JobResult_checks_for_missing_comments(self):
        """
        verify that _build_JobResult() checks if ``comments`` is present
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['comments']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), "Missing value for key 'comments'")

    def test_build_JobResult_checks_type_of_comments(self):
        """
        verify that _build_JobResult() checks if ``comments`` is a string
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['comments'] = False
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'comments' is of incorrect type bool")

    def test_build_JobResult_allows_for_none_comments(self):
        """
        verify that _build_JobResult() allows for the value of ``comments``
        to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['comments'] = None
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.comments, None)

    def test_build_JobResult_restores_comments(self):
        """
        verify that _build_JobResult() restores the value of ``comments``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['comments'] = 'this is a comment'
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.comments, 'this is a comment')

    def test_build_JobResult_checks_for_missing_return_code(self):
        """
        verify that _build_JobResult() checks if ``return_code`` is present
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['return_code']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), "Missing value for key 'return_code'")

    def test_build_JobResult_checks_type_of_return_code(self):
        """
        verify that _build_JobResult() checks if ``return_code`` is an integer
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['return_code'] = "text"
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'return_code' is of incorrect type str")

    def test_build_JobResult_allows_for_none_return_code(self):
        """
        verify that _build_JobResult() allows for the value of ``return_code``
        to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['return_code'] = None
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.return_code, None)

    def test_build_JobResult_restores_return_code(self):
        """
        verify that _build_JobResult() restores the value of ``return_code``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['return_code'] = 42
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.return_code, 42)

    def test_build_JobResult_checks_for_missing_execution_duration(self):
        """
        verify that _build_JobResult() checks if ``execution_duration``
        is present
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['execution_duration']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), "Missing value for key 'execution_duration'")

    def test_build_JobResult_checks_type_of_execution_duration(self):
        """
        verify that _build_JobResult() checks if ``execution_duration``
        is a float
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['execution_duration'] = "text"
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'execution_duration' is of incorrect type str")

    def test_build_JobResult_allows_for_none_execution_duration(self):
        """
        verify that _build_JobResult() allows for the value of
        ``execution_duration`` to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['execution_duration'] = None
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.execution_duration, None)

    def test_build_JobResult_restores_execution_duration(self):
        """
        verify that _build_JobResult() restores the value of
        ``execution_duration``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['execution_duration'] = 5.1
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertAlmostEqual(obj.execution_duration, 5.1)


class MemoryJobResultResumeTests(JobResultResumeMixIn, TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and how they
    handle recreating MemoryJobResult form their representations
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,))
    good_repr = {
        'outcome': "pass",
        'comments': None,
        'return_code': None,
        'execution_duration': None,
        'io_log': []
    }

    def test_build_JobResult_restores_MemoryJobResult_representations(self):
        obj = self.parameters.resume_cls._build_JobResult(self.good_repr)
        self.assertIsInstance(obj, MemoryJobResult)

    def test_build_JobResult_checks_for_missing_io_log(self):
        """
        verify that _build_JobResult() checks if ``io_log`` is present
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['io_log']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception), "Missing value for key 'io_log'")

    def test_build_JobResult_checks_type_of_io_log(self):
        """
        verify that _build_JobResult() checks if ``io_log``
        is a list
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['io_log'] = "text"
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'io_log' is of incorrect type str")

    def test_build_JobResult_checks_for_none_io_log(self):
        """
        verify that _build_JobResult() checks if the value of
        ``io_log`` is not None
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['io_log'] = None
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'io_log' cannot be None")

    def test_build_JobResult_restores_io_log(self):
        """
        verify that _build_JobResult() checks if ``io_log``
        is restored for MemoryJobResult representations
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['io_log'] = [[0.0, 'stdout', '']]
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        # NOTE: MemoryJobResult.io_log is a property that converts
        # whatever was stored to IOLogRecord and returns a _tuple_
        # so the original list is not visible
        self.assertEqual(obj.io_log, tuple([
            IOLogRecord(0.0, 'stdout', b'')
        ]))


class DiskJobResultResumeTests(JobResultResumeMixIn, TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and how they
    handle recreating DiskJobResult form their representations
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,))
    good_repr = {
        'outcome': "pass",
        'comments': None,
        'return_code': None,
        'execution_duration': None,
        'io_log_filename': "file.txt"
    }

    def test_build_JobResult_restores_DiskJobResult_representations(self):
        obj = self.parameters.resume_cls._build_JobResult(self.good_repr)
        self.assertIsInstance(obj, DiskJobResult)

    def test_build_JobResult_does_not_check_for_missing_io_log_filename(self):
        """
        verify that _build_JobResult() does not check if
        ``io_log_filename`` is present as that signifies that MemoryJobResult
        should be recreated instead
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            del obj_repr['io_log_filename']
            self.parameters.resume_cls._build_JobResult(obj_repr)
        # NOTE: the error message explicitly talks about 'io_log', not
        # about 'io_log_filename' because we're hitting the other path
        # of the restore function
        self.assertEqual(
            str(boom.exception), "Missing value for key 'io_log'")

    def test_build_JobResult_checks_type_of_io_log_filename(self):
        """
        verify that _build_JobResult() checks if ``io_log_filename``
        is a string
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['io_log_filename'] = False
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'io_log_filename' is of incorrect type bool")

    def test_build_JobResult_checks_for_none_io_log_filename(self):
        """
        verify that _build_JobResult() checks if the value of
        ``io_log_filename`` is not None
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['io_log_filename'] = None
            self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'io_log_filename' cannot be None")

    def test_build_JobResult_restores_io_log_filename(self):
        """
        verify that _build_JobResult() restores the value of
        ``io_log_filename`` DiskJobResult representations
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['io_log_filename'] = "some-file.txt"
        obj = self.parameters.resume_cls._build_JobResult(obj_repr)
        self.assertEqual(obj.io_log_filename, "some-file.txt")


class DesiredJobListResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and how they
    handle recreating SessionState.desired_job_list form its representation
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,))

    def setUp(self):
        # All of the tests need a SessionState object and some jobs to work
        # with. Actual values don't matter much.
        self.job_a = make_job(name='a')
        self.job_b = make_job(name='b')
        self.session = SessionState([self.job_a, self.job_b])
        self.good_repr = {
            "desired_job_list": ['a', 'b']
        }
        self.resume_fn = (
            self.parameters.resume_cls._restore_SessionState_desired_job_list)

    def test_restore_SessionState_desired_job_list_checks_for_repr_type(self):
        """
        verify that _restore_SessionState_desired_job_list() checks the
        type of the representation of ``desired_job_list``.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['desired_job_list'] = 1
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'desired_job_list' is of incorrect type int")

    def test_restore_SessionState_desired_job_list_checks_job_name_type(self):
        """
        verify that _restore_SessionState_desired_job_list() checks the
        type of each job name listed in ``desired_job_list``.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['desired_job_list'] = [1]
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(str(boom.exception), "Each job name must be a string")

    def test_restore_SessionState_desired_job_list_checks_for_bogus_jobs(self):
        """
        verify that _restore_SessionState_desired_job_list() checks if
        each of the mentioned jobs are known and defined in the session
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['desired_job_list'] = ['bogus']
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(
            str(boom.exception),
            "'desired_job_list' refers to unknown job 'bogus'")

    def test_restore_SessionState_desired_job_list_works(self):
        """
        verify that _restore_SessionState_desired_job_list() actually
        restores desired_job_list on the session
        """
        self.assertEqual(
            self.session.desired_job_list, [])
        self.resume_fn(self.session, self.good_repr)
        # Good representation has two jobs, 'a' and 'b', in that order
        self.assertEqual(
            self.session.desired_job_list,
            [self.job_a, self.job_b])


class SessionMetaDataResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and how they
    handle recreating SessionMetaData form its representation
    """

    parameter_names = ('format',)
    parameter_values = ((1,), (2,))
    good_repr_v1 = {
        "metadata": {
            "title": "some title",
            "flags": ["flag1", "flag2"],
            "running_job_name": "job1"
        }
    }
    good_repr_v2 = {
        "metadata": {
            "title": "some title",
            "flags": ["flag1", "flag2"],
            "running_job_name": "job1",
            "app_blob": None,
        }
    }
    good_repr_map = {
        1: good_repr_v1,
        2: good_repr_v2
    }
    resume_cls_map = {
        1: SessionResumeHelper1,
        2: SessionResumeHelper2,
    }

    def setUp(self):
        # All of the tests need a SessionState object
        self.session = SessionState([])
        self.good_repr = copy.deepcopy(
            self.good_repr_map[self.parameters.format])
        self.resume_fn = (
            self.resume_cls_map[
                self.parameters.format
            ]._restore_SessionState_metadata)

    def test_restore_SessionState_metadata_cheks_for_representation_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        the representation object
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata'] = 1
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'metadata' is of incorrect type int")

    def test_restore_SessionState_metadata_checks_title_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        the ``title`` field.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata']['title'] = 1
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'title' is of incorrect type int")

    def test_restore_SessionState_metadata_allows_for_none_title(self):
        """
        verify that _restore_SessionState_metadata() allows for
        ``title`` to be None
        """
        self.good_repr['metadata']['title'] = None
        self.resume_fn(self.session, self.good_repr)
        self.assertEqual(self.session.metadata.title, None)

    def test_restore_SessionState_metadata_restores_title(self):
        """
        verify that _restore_SessionState_metadata() restores ``title``
        """
        self.good_repr['metadata']['title'] = "a title"
        self.resume_fn(self.session, self.good_repr)
        self.assertEqual(self.session.metadata.title, "a title")

    def test_restore_SessionState_metadata_checks_flags_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        the ``flags`` field.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata']['flags'] = 1
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'flags' is of incorrect type int")

    def test_restore_SessionState_metadata_cheks_if_flags_are_none(self):
        """
        verify that _restore_SessionState_metadata() checks if
        ``flags`` are None
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata']['flags'] = None
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'flags' cannot be None")

    def test_restore_SessionState_metadata_checks_type_of_each_flag(self):
        """
        verify that _restore_SessionState_metadata() checks the type of each
        value of ``flags``
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata']['flags'] = [1]
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Each flag must be a string")

    def test_restore_SessionState_metadata_restores_flags(self):
        """
        verify that _restore_SessionState_metadata() restores ``flags``
        """
        self.good_repr['metadata']['flags'] = ["flag1", "flag2"]
        self.resume_fn(self.session, self.good_repr)
        self.assertEqual(self.session.metadata.flags, set(['flag1', 'flag2']))

    def test_restore_SessionState_metadata_checks_running_job_name_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        ``running_job_name``.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            self.good_repr['metadata']['running_job_name'] = 1
            self.resume_fn(self.session, self.good_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'running_job_name' is of incorrect type int")

    def test_restore_SessionState_metadata_allows__none_running_job_name(self):
        """
        verify that _restore_SessionState_metadata() allows for
        ``running_job_name`` to be None
        """
        self.good_repr['metadata']['running_job_name'] = None
        self.resume_fn(self.session, self.good_repr)
        self.assertEqual(self.session.metadata.running_job_name, None)

    def test_restore_SessionState_metadata_restores_running_job_name(self):
        """
        verify that _restore_SessionState_metadata() restores
        the value of ``running_job_name``
        """
        self.good_repr['metadata']['running_job_name'] = "a job"
        self.resume_fn(self.session, self.good_repr)
        self.assertEqual(self.session.metadata.running_job_name, "a job")


class SessionMetaDataResumeTests2(TestCase):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper2`
    and how it handles recreating SessionMetaData form its representation
    """

    def setUp(self):
        # All of the tests need a SessionState object
        self.session = SessionState([])
        self.good_repr = {
            "metadata": {
                "title": "some title",
                "flags": ["flag1", "flag2"],
                "running_job_name": "job1",
                "app_blob": "YmxvYg=="  # this is b'blob', encoded
            }
        }
        self.resume_fn = SessionResumeHelper2._restore_SessionState_metadata

    def test_restore_SessionState_metadata_checks_app_blob_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        the ``app_blob`` field.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['metadata']['app_blob'] = 1
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'app_blob' is of incorrect type int")

    def test_restore_SessionState_metadata_allows_for_none_app_blob(self):
        """
        verify that _restore_SessionState_metadata() allows for
        ``title`` to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['metadata']['app_blob'] = None
        self.resume_fn(self.session, obj_repr)
        self.assertEqual(self.session.metadata.app_blob, None)

    def test_restore_SessionState_metadata_restores_app_blob(self):
        """
        verify that _restore_SessionState_metadata() restores ``title``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['metadata']['app_blob'] = "YmxvYg=="
        self.resume_fn(self.session, obj_repr)
        self.assertEqual(self.session.metadata.app_blob, b"blob")

    def test_restore_SessionState_metadata_non_ascii_app_blob(self):
        """
        verify that _restore_SessionState_metadata() checks that ``app_blob``
        is ASCII
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['metadata']['app_blob'] = '\uFFFD'
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(str(boom.exception), "app_blob is not ASCII")
        self.assertIsInstance(boom.exception.__context__, UnicodeEncodeError)

    def test_build_SessionState_metadata_non_base64_app_blob(self):
        """
        verify that _restore_SessionState_metadata() checks that ``app_blob``
        is valid base64
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['metadata']['app_blob'] = '==broken'
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(str(boom.exception), "Cannot base64 decode app_blob")
        # base64.standard_b64decode() raises binascii.Error
        self.assertIsInstance(boom.exception.__context__, binascii.Error)


class ProcessJobTests(TestCase):

    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`
    and how it handles processing jobs using _process_job() method
    """

    def setUp(self):
        self.job_name = 'job'
        self.job = make_job(name=self.job_name)
        self.jobs_repr = {
            self.job_name: self.job.get_checksum()
        }
        self.results_repr = {
            self.job_name: [{
                'outcome': 'fail',
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [],
            }]
        }
        self.helper = SessionResumeHelper1([self.job])
        # This object is artificial and would be constructed internally
        # by the helper but having it here makes testing easier as we
        # can reliably test a single method in isolation.
        self.session = SessionState([self.job])

    def test_process_job_checks_type_of_job_name(self):
        """
        verify that _process_job() checks the type of ``job_name``
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            # Pass a job name of the wrong type
            job_name = 1
            self.helper._process_job(
                self.session, self.jobs_repr, self.results_repr, job_name)
        self.assertEqual(
            str(boom.exception), "Value of object is of incorrect type int")

    def test_process_job_checks_for_missing_checksum(self):
        """
        verify that _process_job() checks if ``checksum`` is missing
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            # Pass a jobs_repr that has no checksums (for any job)
            jobs_repr = {}
            self.helper._process_job(
                self.session, jobs_repr, self.results_repr, self.job_name)
        self.assertEqual(str(boom.exception), "Missing value for key 'job'")

    def test_process_job_checks_if_job_is_known(self):
        """
        verify that _process_job() checks if job is known or raises KeyError
        """
        with self.assertRaises(KeyError) as boom:
            # Pass a session that does not know about any jobs
            session = SessionState([])
            self.helper._process_job(
                session, self.jobs_repr, self.results_repr, self.job_name)
        self.assertEqual(boom.exception.args[0], 'job')

    def test_process_job_checks_if_job_checksum_matches(self):
        """
        verify that _process_job() checks if job checksum matches the
        checksum of a job with the same name that was passed to the helper.
        """
        with self.assertRaises(IncompatibleJobError) as boom:
            # Pass a jobs_repr with a bad checksum
            jobs_repr = {self.job_name: 'bad-checksum'}
            self.helper._process_job(
                self.session, jobs_repr, self.results_repr, self.job_name)
        self.assertEqual(
            str(boom.exception), "Definition of job 'job' has changed")

    def test_process_job_handles_ignores_empty_results(self):
        """
        verify that _process_job() does not crash if we have no results
        for a particular job
        """
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, None)
        results_repr = {
            self.job_name: []
        }
        self.helper._process_job(
            self.session, self.jobs_repr, results_repr, self.job_name)
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, None)

    def test_process_job_handles_only_result_back_to_the_session(self):
        """
        verify that _process_job() passes the only result to the session
        """
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, None)
        self.helper._process_job(
            self.session, self.jobs_repr, self.results_repr, self.job_name)
        # The result in self.results_repr is a failure so we should see it here
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, "fail")

    def test_process_job_handles_last_result_back_to_the_session(self):
        """
        verify that _process_job() passes last of the results to the session
        """
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, None)
        results_repr = {
            self.job_name: [{
                'outcome': 'fail',
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [],
            }, {
                'outcome': 'pass',
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [],
            }]
        }
        self.helper._process_job(
            self.session, self.jobs_repr, results_repr, self.job_name)
        # results_repr has two entries: [fail, pass] so we should see
        # the passing entry only
        self.assertEqual(
            self.session.job_state_map[self.job_name].result.outcome, "pass")

    def test_process_job_checks_results_repr_is_a_list(self):
        """
        verify that _process_job() checks if results_repr is a dictionary
        of lists.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            results_repr = {self.job_name: 1}
            self.helper._process_job(
                self.session, self.jobs_repr, results_repr, self.job_name)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'job' is of incorrect type int")

    def test_process_job_checks_results_repr_values_are_dicts(self):
        """
        verify that _process_job() checks if results_repr is a dictionary
        of lists, each of which holds a dictionary.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            results_repr = {self.job_name: [1]}
            self.helper._process_job(
                self.session, self.jobs_repr, results_repr, self.job_name)
        self.assertEqual(
            str(boom.exception),
            "Value of object is of incorrect type int")


class JobPluginSpecificTests(TestCase):

    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`
    and how it handles processing jobs using _process_job() method. This
    class focuses on plugin-specific test such as for local and resource jobs
    """

    def test_process_job_restores_resources(self):
        """
        verify that _process_job() recreates resources
        """
        # Set the stage for testing. Setup a session with a known
        # resource job, representation of the job (checksum)
        # and representation of a single result, which has a single line
        # that defines a 'key': 'value' resource record.
        job_name = 'resource'
        job = make_job(name=job_name, plugin='resource')
        jobs_repr = {
            job_name: job.get_checksum()
        }
        results_repr = {
            job_name: [{
                'outcome': None,
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [
                    # A bit convoluted but this is how we encode each chunk
                    # of IOLogRecord
                    [0.0, 'stdout', base64.standard_b64encode(
                        b'key: value'
                    ).decode('ASCII')]
                ],
            }]
        }
        helper = SessionResumeHelper1([job])
        session = SessionState([job])
        # Ensure that the resource was not there initially
        self.assertNotIn(job_name, session.resource_map)
        # Process the representation data defined above
        helper._process_job(session, jobs_repr, results_repr, job_name)
        # Ensure that we now have the resource in the resource map
        self.assertIn(job_name, session.resource_map)
        # And that it looks right
        self.assertEqual(
            session.resource_map[job_name],
            [Resource({'key': 'value'})])

    def test_process_job_restores_jobs(self):
        """
        verify that _process_job() recreates generated jobs
        """
        # Set the stage for testing. Setup a session with a known
        # local job, representation of the job (checksum)
        # and representation of a single result, which has a single line
        # that defines a 'name': 'generated' job.
        job_name = 'local'
        job = make_job(name=job_name, plugin='local')
        jobs_repr = {
            job_name: job.get_checksum()
        }
        results_repr = {
            job_name: [{
                'outcome': None,
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [
                    [0.0, 'stdout', base64.standard_b64encode(
                        b'name: generated'
                    ).decode('ASCII')]
                ],
            }]
        }
        helper = SessionResumeHelper1([job])
        session = SessionState([job])
        # Ensure that the 'generated' job was not there initially
        self.assertNotIn('generated', session.job_state_map)
        self.assertEqual(session.job_list, [job])
        # Process the representation data defined above
        helper._process_job(session, jobs_repr, results_repr, job_name)
        # Ensure that we now have the 'generated' job in the job_state_map
        self.assertIn('generated', session.job_state_map)
        # And that it looks right
        self.assertEqual(
            session.job_state_map['generated'].job.name, 'generated')
        self.assertIn(
            session.job_state_map['generated'].job, session.job_list)


class SessionJobsAndResultsResumeTests(TestCase):

    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`
    and how it handles resume the session using
    _restore_SessionState_jobs_and_results() method.
    """

    def test_empty_session(self):
        """
        verify that _restore_SessionState_jobs_and_results() works when
        faced with a representation of an empty session. This is mostly
        to do sanity checking on the 'easy' parts of the code before
        testing specific cases in the rest of the code.
        """
        session_repr = {
            'jobs': {},
            'results': {}
        }
        helper = SessionResumeHelper1([])
        session = SessionState([])
        helper._restore_SessionState_jobs_and_results(session, session_repr)
        self.assertEqual(session.job_list, [])
        self.assertEqual(session.resource_map, {})
        self.assertEqual(session.job_state_map, {})

    def test_simple_session(self):
        """
        verify that _restore_SessionState_jobs_and_results() works when
        faced with a representation of a simple session (no generated jobs
        or anything "exotic").
        """
        job = make_job(name='job')
        session_repr = {
            'jobs': {
                job.name: job.get_checksum(),
            },
            'results': {
                job.name: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [],
                }]
            }
        }
        helper = SessionResumeHelper1([job])
        session = SessionState([job])
        helper._restore_SessionState_jobs_and_results(session, session_repr)
        # Session still has one job in it
        self.assertEqual(session.job_list, [job])
        # Resources don't have anything (no resource jobs)
        self.assertEqual(session.resource_map, {})
        # The result was restored correctly. This is just a smoke test
        # as specific tests for restoring results are written elsewhere
        self.assertEqual(
            session.job_state_map[job.name].result.outcome, 'pass')

    def test_session_with_generated_jobs(self):
        """
        verify that _restore_SessionState_jobs_and_results() works when
        faced with a representation of a non-trivial session where one
        job generates another one.
        """
        parent = make_job(name='parent', plugin='local')
        # The child job is only here so that we can get the checksum.
        # We don't actually introduce it into the resume machinery
        # caveat: make_job() has a default value for
        # plugin='dummy' which we don't want here
        child = make_job(name='child', plugin=None)
        session_repr = {
            'jobs': {
                parent.name: parent.get_checksum(),
                child.name: child.get_checksum(),
            },
            'results': {
                parent.name: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'name: child\n'
                        ).decode('ASCII')]
                    ],
                }],
                child.name: [],
            }
        }
        # We only pass the parent to the helper! Child will be re-created
        helper = SessionResumeHelper1([parent])
        session = SessionState([parent])
        helper._restore_SessionState_jobs_and_results(session, session_repr)
        # We should now have two jobs, parent and child
        self.assertEqual(session.job_list, [parent, child])
        # Resources don't have anything (no resource jobs)
        self.assertEqual(session.resource_map, {})

    def test_session_with_generated_jobs2(self):
        """
        verify that _restore_SessionState_jobs_and_results() works when
        faced with a representation of a non-trivial session where one
        job generates another one and that one generates one more.
        """
        # XXX: Important information about this test.
        # This test uses a very subtle ordering of jobs to achieve
        # the desired testing effect. This does not belong in this test case
        # and should be split into a dedicated, very well documented method
        # The only information I'll leave here now is that
        # _restore_SessionState_jobs_and_results() is processing jobs
        # in alphabetical order. This coupled with ordering:
        # a_grandparent (generated)
        # b_child (generated)
        # c_parent
        # creates the most pathological case possible.
        parent = make_job(name='c_parent', plugin='local')
        # The child job is only here so that we can get the checksum.
        # We don't actually introduce it into the resume machinery
        child = make_job(name='b_child', plugin='local')
        # caveat: make_job() has a default value for
        # plugin='dummy' which we don't want here
        grandchild = make_job(name='a_grandchild', plugin=None)
        session_repr = {
            'jobs': {
                parent.name: parent.get_checksum(),
                child.name: child.get_checksum(),
                grandchild.name: grandchild.get_checksum(),
            },
            'results': {
                parent.name: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'name: b_child\n'
                        ).decode('ASCII')],
                        [0.1, 'stdout', base64.standard_b64encode(
                            b'plugin: local\n'
                        ).decode('ASCII')]

                    ],
                }],
                child.name: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'name: a_grandchild\n'
                        ).decode('ASCII')]
                    ],
                }],
                grandchild.name: [],
            }
        }
        # We only pass the parent to the helper!
        # The 'child' and 'grandchild' jobs will be re-created
        helper = SessionResumeHelper1([parent])
        session = SessionState([parent])
        helper._restore_SessionState_jobs_and_results(session, session_repr)
        # We should now have two jobs, parent and child
        self.assertEqual(session.job_list, [parent, child, grandchild])
        # Resources don't have anything (no resource jobs)
        self.assertEqual(session.resource_map, {})

    def test_unknown_jobs_get_reported(self):
        """
        verify that _restore_SessionState_jobs_and_results() reports
        all unresolved jobs (as CorruptedSessionError exception)
        """
        session_repr = {
            'jobs': {
                'job-name': 'job-checksum',
            },
            'results': {
                'job-name': []
            }
        }
        helper = SessionResumeHelper1([])
        session = SessionState([])
        with self.assertRaises(CorruptedSessionError) as boom:
            helper._restore_SessionState_jobs_and_results(
                session, session_repr)
        self.assertEqual(
            str(boom.exception), "Unknown jobs remaining: job-name")
