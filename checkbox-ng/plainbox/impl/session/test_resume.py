# This file is part of Checkbox.
#
# Copyright 2012, 2013, 2014 Canonical Ltd.
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

from plainbox.abc import IJobQualifier
from plainbox.impl.job import JobDefinition
from plainbox.impl.resource import Resource
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.resume import CorruptedSessionError
from plainbox.impl.session.resume import IncompatibleJobError
from plainbox.impl.session.resume import IncompatibleSessionError
from plainbox.impl.session.resume import ResumeDiscardQualifier
from plainbox.impl.session.resume import SessionResumeError
from plainbox.impl.session.resume import SessionResumeHelper
from plainbox.impl.session.resume import SessionResumeHelper1
from plainbox.impl.session.resume import SessionResumeHelper2
from plainbox.impl.session.resume import SessionResumeHelper3
from plainbox.impl.session.state import SessionState
from plainbox.impl.testing_utils import make_job
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor import mock


class ResumeDiscardQualifierTests(TestCase):
    """
    Tests for the ResumeDiscardQualifier class
    """

    def setUp(self):
        # The initializer accepts the jobs representation dictionary but uses
        # keys only. Here the values are dummy None objects
        self.obj = ResumeDiscardQualifier({'foo': None, 'bar': None})

    def test_init(self):
        self.assertEqual(self.obj._retain_id_set, frozenset(['foo', 'bar']))

    def test_get_simple_match(self):
        # Direct hits return the IGNORE vote as those jobs are not to be
        # removed. Everything else should return VOTE_INCLUDE (include for
        # removal)
        self.assertEqual(
            self.obj.get_vote(JobDefinition({'id': 'foo'})),
            IJobQualifier.VOTE_IGNORE)
        self.assertEqual(
            self.obj.get_vote(JobDefinition({'id': 'bar'})),
            IJobQualifier.VOTE_IGNORE)
        # Jobs that are in the retain set are NOT designated
        self.assertEqual(
            self.obj.designates(JobDefinition({'id': 'bar'})), False)
        self.assertEqual(
            self.obj.designates(JobDefinition({'id': 'foo'})), False)
        # Jobs that are not on the retain list are INCLUDED and marked for
        # removal. This includes jobs that are substrings of strings in the
        # retain set, ids are matched exactly, not by pattern.
        self.assertEqual(
            self.obj.get_vote(JobDefinition({'id': 'foobar'})),
            IJobQualifier.VOTE_INCLUDE)
        self.assertEqual(
            self.obj.get_vote(JobDefinition({'id': 'fo'})),
            IJobQualifier.VOTE_INCLUDE)


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

    @mock.patch('plainbox.impl.session.resume.SessionResumeHelper3')
    def test_resume_dispatch_v3(self, mocked_helper3):
        data = gzip.compress(
            b'{"session":{"desired_job_list":[],"jobs":{},"metadata":'
            b'{"app_blob":null,"app_id":null,"flags":[],'
            b'"running_job_name":null,"title":null'
            b'},"results":{}},"version":3}')
        SessionResumeHelper([]).resume(data)
        mocked_helper3.resume_json.assertCalledOnce()

    def test_resume_dispatch_v4(self):
        data = gzip.compress(
            b'{"version":4}')
        with self.assertRaises(IncompatibleSessionError) as boom:
            SessionResumeHelper([]).resume(data)
        self.assertEqual(str(boom.exception), "Unsupported version 4")


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
    parameter_values = (('1',), ('2',), ('3',))

    full_repr_1 = {
        'version': 1,
        'session': {
            'jobs': {
                '__category__': (
                    'e2475434e4c0b2c825541430e526fe0565780dfeb67'
                    '050f3b7f3453aa3cc439b'),
                'generator': (
                    'b2aa7b7c4298678cebfdbe30f4aae5be97d320910a5'
                    'b4dd312606099f35c03b6'),
                'generated': (
                    '57b395e91bb4af94143eb19586bd18e4013efc5e60d'
                    '6050d9ec0bea15dd19489'),
            },
            'results': {
                '__category__': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [
                        [0.0, 'stdout', 'cGx1Z2luOmxvY2FsCg=='],
                        [0.1, 'stdout', 'aWQ6Z2VuZXJhdG9yCg==']],
                    'outcome': None,
                    'return_code': None,
                }],
                'generator': [{
                    'comments': None,
                    'execution_duration': None,
                    'io_log': [
                        [0.0, 'stdout', 'aWQ6Z2VuZXJhdGVk']],
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

    # Copy and patch the v2 representation to get a v3 representation
    full_repr_3 = copy.deepcopy(full_repr_2)
    full_repr_3['version'] = 3
    full_repr_3['session']['metadata']['app_id'] = None

    # Map of representation ids to representations
    full_repr = {
        '1': full_repr_1,
        '2': full_repr_2,
        '3': full_repr_3
    }

    def setUp(self):
        # Crete a "__category__" job
        self.category_job = JobDefinition({
            "plugin": "local",
            "id": "__category__"
        })
        # Create a "generator" job
        self.generator_job = JobDefinition({
            "plugin": "local",
            "id": "generator"
        })
        # Keep a variable for the (future) generated job
        self.generated_job = None
        # Create a result for the "__category__" job.
        # It must define a verbatim copy of the "generator" job
        self.category_result = MemoryJobResult({
            "io_log": [
                (0.0, "stdout", b'plugin:local\n'),
                (0.1, "stdout", b'id:generator\n'),
            ]
        })
        # Create a result for the "generator" job.
        # It will define the "generated" job
        self.generator_result = MemoryJobResult({
            "io_log": [(0.0, 'stdout', b'id:generated')]
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


class SessionStateResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle resuming SessionState inside _build_SessionState() method.
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

    def setUp(self):
        self.session_repr = {}
        self.helper = self.parameters.resume_cls([])

    def test_calls_build_SessionState(self):
        """
        verify that _build_SessionState() gets called
        """
        with mock.patch.object(self.helper, attribute='_build_SessionState'):
            self.helper._build_SessionState(self.session_repr)
            self.helper._build_SessionState.assertCalledOnceWith(
                self.session_repr, None)

    def test_calls_restore_SessionState_jobs_and_results(self):
        """
        verify that _restore_SessionState_jobs_and_results() gets called by
        _build_SessionState().
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_build_SessionState'), \
                mpo(self.helper, '_restore_SessionState_jobs_and_results'):
            session = self.helper._build_SessionState(self.session_repr)
            self.helper._restore_SessionState_jobs_and_results. \
                assertCalledOnceWith(session, self.session_repr)

    def test_calls_restore_SessionState_metadata(self):
        """
        verify that _restore_SessionState_metadata() gets called by
        _build_SessionState().
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_build_SessionState'), \
                mpo(self.helper, '_restore_SessionState_metadata'):
            session = self.helper._build_SessionState(self.session_repr)
            self.helper._restore_SessionState_metadata. \
                assertCalledOnceWith(session, self.session_repr)

    def test_calls_restore_SessionState_desired_job_list(self):
        """
        verify that _restore_SessionState_desired_job_list() gets called by
        _build_SessionState().
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_build_SessionState'), \
                mpo(self.helper, '_restore_SessionState_desired_job_list'):
            session = self.helper._build_SessionState(self.session_repr)
            self.helper._restore_SessionState_desired_job_list. \
                assertCalledOnceWith(session, self.session_repr)

    def test_calls_restore_SessionState_job_list(self):
        """
        verify that _restore_SessionState_job_list() gets called by
        _build_SessionState().
        """
        mpo = mock.patch.object
        with mpo(self.helper, '_build_SessionState'), \
                mpo(self.helper, '_restore_SessionState_job_list'):
            session = self.helper._build_SessionState(self.session_repr)
            self.helper._restore_SessionState_job_list.assertCalledOnceWith(
                session, self.session_repr)


class IOLogRecordResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle resuming IOLogRecord objects
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

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
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle recreating MemoryJobResult form their representations
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))
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
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle recreating DiskJobResult form their representations
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))
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
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle recreating SessionState.desired_job_list form its representation
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

    def setUp(self):
        # All of the tests need a SessionState object and some jobs to work
        # with. Actual values don't matter much.
        self.job_a = make_job(id='a')
        self.job_b = make_job(id='b')
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

    def test_restore_SessionState_desired_job_list_checks_job_id_type(self):
        """
        verify that _restore_SessionState_desired_job_list() checks the
        type of each job id listed in ``desired_job_list``.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['desired_job_list'] = [1]
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(str(boom.exception), "Each job id must be a string")

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
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle recreating SessionMetaData form its representation
    """

    parameter_names = ('format',)
    parameter_values = ((1,), (2,), (3,))
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
    good_repr_v3 = {
        "metadata": {
            "title": "some title",
            "flags": ["flag1", "flag2"],
            "running_job_name": "job1",
            "app_blob": None,
            "app_id": None,
        }
    }
    good_repr_map = {
        1: good_repr_v1,
        2: good_repr_v2,
        3: good_repr_v3
    }
    resume_cls_map = {
        1: SessionResumeHelper1,
        2: SessionResumeHelper2,
        3: SessionResumeHelper3,
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
        ``app_blob`` to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['metadata']['app_blob'] = None
        self.resume_fn(self.session, obj_repr)
        self.assertEqual(self.session.metadata.app_blob, None)

    def test_restore_SessionState_metadata_restores_app_blob(self):
        """
        verify that _restore_SessionState_metadata() restores ``app_blob``
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

    def test_restore_SessionState_metadata_non_base64_app_blob(self):
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


class SessionMetaDataResumeTest3(SessionMetaDataResumeTests2):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper3`
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
                "app_blob": "YmxvYg==",  # this is b'blob', encoded
                "app_id": "id"
            }
        }
        self.resume_fn = SessionResumeHelper3._restore_SessionState_metadata

    def test_restore_SessionState_metadata_checks_app_id_type(self):
        """
        verify that _restore_SessionState_metadata() checks the type of
        the ``app_id`` field.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            obj_repr = copy.copy(self.good_repr)
            obj_repr['metadata']['app_id'] = 1
            self.resume_fn(self.session, obj_repr)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'app_id' is of incorrect type int")

    def test_restore_SessionState_metadata_allows_for_none_app_id(self):
        """
        verify that _restore_SessionState_metadata() allows for
        ``app_id`` to be None
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['metadata']['app_id'] = None
        self.resume_fn(self.session, obj_repr)
        self.assertEqual(self.session.metadata.app_id, None)

    def test_restore_SessionState_metadata_restores_app_id(self):
        """
        verify that _restore_SessionState_metadata() restores ``app_id``
        """
        obj_repr = copy.copy(self.good_repr)
        obj_repr['metadata']['app_id'] = "id"
        self.resume_fn(self.session, obj_repr)
        self.assertEqual(self.session.metadata.app_id, "id")


class ProcessJobTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2` and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3` and how they
    handle processing jobs using _process_job() method
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

    def setUp(self):
        self.job_id = 'job'
        self.job = make_job(id=self.job_id)
        self.jobs_repr = {
            self.job_id: self.job.checksum
        }
        self.results_repr = {
            self.job_id: [{
                'outcome': 'fail',
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [],
            }]
        }
        self.helper = self.parameters.resume_cls([self.job])
        # This object is artificial and would be constructed internally
        # by the helper but having it here makes testing easier as we
        # can reliably test a single method in isolation.
        self.session = SessionState([self.job])

    def test_process_job_checks_type_of_job_id(self):
        """
        verify that _process_job() checks the type of ``job_id``
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            # Pass a job id of the wrong type
            job_id = 1
            self.helper._process_job(
                self.session, self.jobs_repr, self.results_repr, job_id)
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
                self.session, jobs_repr, self.results_repr, self.job_id)
        self.assertEqual(str(boom.exception), "Missing value for key 'job'")

    def test_process_job_checks_if_job_is_known(self):
        """
        verify that _process_job() checks if job is known or raises KeyError
        """
        with self.assertRaises(KeyError) as boom:
            # Pass a session that does not know about any jobs
            session = SessionState([])
            self.helper._process_job(
                session, self.jobs_repr, self.results_repr, self.job_id)
        self.assertEqual(boom.exception.args[0], 'job')

    def test_process_job_checks_if_job_checksum_matches(self):
        """
        verify that _process_job() checks if job checksum matches the
        checksum of a job with the same id that was passed to the helper.
        """
        with self.assertRaises(IncompatibleJobError) as boom:
            # Pass a jobs_repr with a bad checksum
            jobs_repr = {self.job_id: 'bad-checksum'}
            self.helper._process_job(
                self.session, jobs_repr, self.results_repr, self.job_id)
        self.assertEqual(
            str(boom.exception), "Definition of job 'job' has changed")

    def test_process_job_handles_ignores_empty_results(self):
        """
        verify that _process_job() does not crash if we have no results
        for a particular job
        """
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, None)
        results_repr = {
            self.job_id: []
        }
        self.helper._process_job(
            self.session, self.jobs_repr, results_repr, self.job_id)
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, None)

    def test_process_job_handles_only_result_back_to_the_session(self):
        """
        verify that _process_job() passes the only result to the session
        """
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, None)
        self.helper._process_job(
            self.session, self.jobs_repr, self.results_repr, self.job_id)
        # The result in self.results_repr is a failure so we should see it here
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, "fail")

    def test_process_job_handles_last_result_back_to_the_session(self):
        """
        verify that _process_job() passes last of the results to the session
        """
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, None)
        results_repr = {
            self.job_id: [{
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
            self.session, self.jobs_repr, results_repr, self.job_id)
        # results_repr has two entries: [fail, pass] so we should see
        # the passing entry only
        self.assertEqual(
            self.session.job_state_map[self.job_id].result.outcome, "pass")

    def test_process_job_checks_results_repr_is_a_list(self):
        """
        verify that _process_job() checks if results_repr is a dictionary
        of lists.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            results_repr = {self.job_id: 1}
            self.helper._process_job(
                self.session, self.jobs_repr, results_repr, self.job_id)
        self.assertEqual(
            str(boom.exception),
            "Value of key 'job' is of incorrect type int")

    def test_process_job_checks_results_repr_values_are_dicts(self):
        """
        verify that _process_job() checks if results_repr is a dictionary
        of lists, each of which holds a dictionary.
        """
        with self.assertRaises(CorruptedSessionError) as boom:
            results_repr = {self.job_id: [1]}
            self.helper._process_job(
                self.session, self.jobs_repr, results_repr, self.job_id)
        self.assertEqual(
            str(boom.exception),
            "Value of object is of incorrect type int")


class JobPluginSpecificTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle processing jobs using _process_job() method. This class focuses on
    plugin-specific test such as for local and resource jobs
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

    def test_process_job_restores_resources(self):
        """
        verify that _process_job() recreates resources
        """
        # Set the stage for testing. Setup a session with a known
        # resource job, representation of the job (checksum)
        # and representation of a single result, which has a single line
        # that defines a 'key': 'value' resource record.
        job_id = 'resource'
        job = make_job(id=job_id, plugin='resource')
        jobs_repr = {
            job_id: job.checksum
        }
        results_repr = {
            job_id: [{
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
        helper = self.parameters.resume_cls([job])
        session = SessionState([job])
        # Ensure that the resource was not there initially
        self.assertNotIn(job_id, session.resource_map)
        # Process the representation data defined above
        helper._process_job(session, jobs_repr, results_repr, job_id)
        # Ensure that we now have the resource in the resource map
        self.assertIn(job_id, session.resource_map)
        # And that it looks right
        self.assertEqual(
            session.resource_map[job_id],
            [Resource({'key': 'value'})])

    def test_process_job_restores_jobs(self):
        """
        verify that _process_job() recreates generated jobs
        """
        # Set the stage for testing. Setup a session with a known
        # local job, representation of the job (checksum)
        # and representation of a single result, which has a single line
        # that defines a 'id': 'generated' job.
        job_id = 'local'
        job = make_job(id=job_id, plugin='local')
        jobs_repr = {
            job_id: job.checksum
        }
        results_repr = {
            job_id: [{
                'outcome': None,
                'comments': None,
                'execution_duration': None,
                'return_code': None,
                'io_log': [
                    [0.0, 'stdout', base64.standard_b64encode(
                        b'id: generated'
                    ).decode('ASCII')]
                ],
            }]
        }
        helper = self.parameters.resume_cls([job])
        session = SessionState([job])
        # Ensure that the 'generated' job was not there initially
        self.assertNotIn('generated', session.job_state_map)
        self.assertEqual(session.job_list, [job])
        # Process the representation data defined above
        helper._process_job(session, jobs_repr, results_repr, job_id)
        # Ensure that we now have the 'generated' job in the job_state_map
        self.assertIn('generated', session.job_state_map)
        # And that it looks right
        self.assertEqual(
            session.job_state_map['generated'].job.id, 'generated')
        self.assertIn(
            session.job_state_map['generated'].job, session.job_list)


class SessionJobsAndResultsResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle resume the session using _restore_SessionState_jobs_and_results()
    method.
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

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
        helper = self.parameters.resume_cls([])
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
        job = make_job(id='job')
        session_repr = {
            'jobs': {
                job.id: job.checksum,
            },
            'results': {
                job.id: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [],
                }]
            }
        }
        helper = self.parameters.resume_cls([])
        session = SessionState([job])
        helper._restore_SessionState_jobs_and_results(session, session_repr)
        # Session still has one job in it
        self.assertEqual(session.job_list, [job])
        # Resources don't have anything (no resource jobs)
        self.assertEqual(session.resource_map, {})
        # The result was restored correctly. This is just a smoke test
        # as specific tests for restoring results are written elsewhere
        self.assertEqual(
            session.job_state_map[job.id].result.outcome, 'pass')

    def test_session_with_generated_jobs(self):
        """
        verify that _restore_SessionState_jobs_and_results() works when
        faced with a representation of a non-trivial session where one
        job generates another one.
        """
        parent = make_job(id='parent', plugin='local')
        # The child job is only here so that we can get the checksum.
        # We don't actually introduce it into the resume machinery
        # caveat: make_job() has a default value for
        # plugin='dummy' which we don't want here
        child = make_job(id='child', plugin=None)
        session_repr = {
            'jobs': {
                parent.id: parent.checksum,
                child.id: child.checksum,
            },
            'results': {
                parent.id: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'id: child\n'
                        ).decode('ASCII')]
                    ],
                }],
                child.id: [],
            }
        }
        # We only pass the parent to the helper! Child will be re-created
        helper = self.parameters.resume_cls([parent])
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
        parent = make_job(id='c_parent', plugin='local')
        # The child job is only here so that we can get the checksum.
        # We don't actually introduce it into the resume machinery
        child = make_job(id='b_child', plugin='local')
        # caveat: make_job() has a default value for
        # plugin='dummy' which we don't want here
        grandchild = make_job(id='a_grandchild', plugin=None)
        session_repr = {
            'jobs': {
                parent.id: parent.checksum,
                child.id: child.checksum,
                grandchild.id: grandchild.checksum,
            },
            'results': {
                parent.id: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'id: b_child\n'
                        ).decode('ASCII')],
                        [0.1, 'stdout', base64.standard_b64encode(
                            b'plugin: local\n'
                        ).decode('ASCII')]

                    ],
                }],
                child.id: [{
                    'outcome': 'pass',
                    'comments': None,
                    'execution_duration': None,
                    'return_code': None,
                    'io_log': [
                        # This record will generate a job identical
                        # to the 'child' job defined above.
                        [0.0, 'stdout', base64.standard_b64encode(
                            b'id: a_grandchild\n'
                        ).decode('ASCII')]
                    ],
                }],
                grandchild.id: [],
            }
        }
        # We only pass the parent to the helper!
        # The 'child' and 'grandchild' jobs will be re-created
        helper = self.parameters.resume_cls([parent])
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
                'job-id': 'job-checksum',
            },
            'results': {
                'job-id': []
            }
        }
        helper = self.parameters.resume_cls([])
        session = SessionState([])
        with self.assertRaises(CorruptedSessionError) as boom:
            helper._restore_SessionState_jobs_and_results(
                session, session_repr)
        self.assertEqual(
            str(boom.exception), "Unknown jobs remaining: job-id")


class SessionJobListResumeTests(TestCaseWithParameters):
    """
    Tests for :class:`~plainbox.impl.session.resume.SessionResumeHelper1`,
    :class:`~plainbox.impl.session.resume.SessionResumeHelper2' and
    :class:`~plainbox.impl.session.resume.SessionResumeHelper3' and how they
    handle resume session.job_list using _restore_SessionState_job_list()
    method.
    """

    parameter_names = ('resume_cls',)
    parameter_values = ((SessionResumeHelper1,), (SessionResumeHelper2,),
                        (SessionResumeHelper3,))

    def test_simple_session(self):
        """
        verify that _restore_SessionState_job_list() does restore job_list
        """
        job_a = make_job(id='a')
        job_b = make_job(id='b')
        session_repr = {
            'jobs': {
                job_a.id: job_a.checksum
            },
            'results': {
                job_a.id: [],
            }
        }
        helper = self.parameters.resume_cls([job_a, job_b])
        session = SessionState([job_a, job_b])
        helper._restore_SessionState_job_list(session, session_repr)
        # Job "a" is still in the list but job "b" got removed
        self.assertEqual(session.job_list, [job_a])
        # The rest is tested by trim_job_list() tests
