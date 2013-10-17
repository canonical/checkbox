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
:mod:`plainbox.impl.session.test_suspend`
=========================================

Test definitions for :mod:`plainbox.impl.session.suspend` module
"""

from functools import partial
from unittest import TestCase
import gzip

from plainbox.impl.job import JobDefinition
from plainbox.impl.result import DiskJobResult
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.session.state import SessionState
from plainbox.impl.session.suspend import SessionSuspendHelper1
from plainbox.impl.session.suspend import SessionSuspendHelper2
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
        self.helper = SessionSuspendHelper1()
        self.empty_result = self.TESTED_CLS({})
        self.typical_result = self.TESTED_CLS({
            "outcome": self.TESTED_CLS.OUTCOME_PASS,
            "execution_duration": 42.5,
            "comments": "the screen was corrupted",
            "return_code": 1,
            # NOTE: those are actually specific to TESTED_CLS but it is
            # a simple hack that gets the job done
            "io_log_filename": "/nonexistent.log",
            "io_log": [
                (0, 'stdout', b'first part\n'),
                (0.1, 'stdout', b'second part\n'),
            ]
        })

    def test_repr_xxxJobResult_outcome(self):
        """
        verify that DiskJobResult.outcome is serialized correctly
        """
        data = self.repr_method(self.typical_result)
        self.assertEqual(data['outcome'], DiskJobResult.OUTCOME_PASS)

    def test_repr_xxxJobResult_execution_duration(self):
        """
        verify that DiskJobResult.execution_duration is serialized correctly
        """
        data = self.repr_method(self.typical_result)
        self.assertAlmostEqual(data['execution_duration'], 42.5)

    def test_repr_xxxJobResult_comments(self):
        """
        verify that DiskJobResult.comments is serialized correctly
        """
        data = self.repr_method(self.typical_result)
        self.assertEqual(data['comments'], "the screen was corrupted")

    def test_repr_xxxJobResult_return_code(self):
        """
        verify that DiskJobResult.return_code is serialized correctly
        """
        data = self.repr_method(self.typical_result)
        self.assertEqual(data['return_code'], 1)


class SuspendMemoryJobResultTests(BaseJobResultTestsTestsMixIn, TestCase):
    """
    Tests that check how MemoryJobResult is represented by SessionSuspendHelper
    """

    TESTED_CLS = MemoryJobResult

    def setUp(self):
        super(SuspendMemoryJobResultTests, self).setUp()
        self.repr_method = self.helper._repr_MemoryJobResult

    def test_repr_MemoryJobResult_empty(self):
        """
        verify that the representation of an empty MemoryJobResult is okay
        """
        data = self.repr_method(self.empty_result)
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
        data = self.helper._repr_MemoryJobResult(self.typical_result)
        self.assertEqual(data['io_log'], [
            [0, 'stdout', 'Zmlyc3QgcGFydAo='],
            [0.1, 'stdout', 'c2Vjb25kIHBhcnQK'],
        ])


class SuspendDiskJobResultTests(BaseJobResultTestsTestsMixIn, TestCase):
    """
    Tests that check how DiskJobResult is represented by SessionSuspendHelper
    """

    TESTED_CLS = DiskJobResult

    def setUp(self):
        super(SuspendDiskJobResultTests, self).setUp()
        self.repr_method = self.helper._repr_DiskJobResult

    def test_repr_DiskJobResult_empty(self):
        """
        verify that the representation of an empty DiskJobResult is okay
        """
        data = self.repr_method(self.empty_result)
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
        data = self.helper._repr_DiskJobResult(self.typical_result)
        self.assertEqual(data['io_log_filename'], "/nonexistent.log")


class SessionSuspendHelper1Tests(TestCase):
    """
    Tests for various methods of SessionSuspendHelper
    """

    def setUp(self):
        self.helper = SessionSuspendHelper1()

    def test_repr_IOLogRecord(self):
        """
        verify that the representation of IOLogRecord is okay
        """
        record = IOLogRecord(0.0, "stdout", b"binary data")
        data = self.helper._repr_IOLogRecord(record)
        self.assertEqual(data, [0.0, "stdout", "YmluYXJ5IGRhdGE="])

    @mock.patch('plainbox.impl.session.suspend.SessionSuspendHelper')
    def test_repr_JobResult_with_MemoryJobResult(self, mocked_helper):
        """
        verify that _repr_JobResult() called with MemoryJobResult
        calls _repr_MemoryJobResult
        """
        result = MemoryJobResult({})
        self.helper._repr_JobResult(result)
        mocked_helper._repr_MemoryJobResult.assertCalledOnceWith(result)

    @mock.patch('plainbox.impl.session.suspend.SessionSuspendHelper')
    def test_repr_JobResult_with_DiskJobResult(self, mocked_helper):
        """
        verify that _repr_JobResult() called with DiskJobResult
        calls _repr_DiskJobResult
        """
        result = DiskJobResult({})
        self.helper._repr_JobResult(result)
        mocked_helper._repr_DiskJobResult.assertCalledOnceWith(result)

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
        data = self.helper._repr_SessionMetaData(SessionMetaData())
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
        ))
        self.assertEqual(data, {
            'title': 'USB Testing session',
            'flags': ['incomplete'],
            'running_job_name': 'usb/detect',
        })

    def test_repr_SessionState_empty_session(self):
        """
        verify that representation of empty SessionState is okay
        """
        data = self.helper._repr_SessionState(SessionState([]))
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
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
        data = self.helper._json_repr(SessionState([]))
        self.assertIn("version", data)

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]))
        self.assertEqual(data['version'], 1)

    def test_json_repr_stores_session_state(self):
        """
        verify that the json representation has the 'session' field
        """
        data = self.helper._json_repr(SessionState([]))
        self.assertIn("session", data)

    def test_suspend(self):
        """
        verify that the suspend() method returns gzipped JSON representation
        """
        data = self.helper.suspend(SessionState([]))
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
            b'{"session":{"desired_job_list":[],"jobs":{},"metadata":'
            b'{"flags":[],"running_job_name":null,"title":null},"results":{}'
            b'},"version":1}'))


class GeneratedJobSuspendTests(TestCase):
    """
    Tests that check how SessionSuspendHelper behaves when faced with
    generated jobs. This tests sets up the following job hierarchy:

        __category__
           \-> generator
                \-> generated

    The "__category__" job is a typical "catter" job that cats an existing
    job from somewhere else in the filesystem. This type of generated job
    is used often for category assignment.

    The "generator" job is a typical non-catter job that actually creates
    new jobs in some way. In this test it generates a job called "generated".
    """

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
        # Create a session that knows about the two jobs that exist
        # directly as files (__category__ and generator)
        self.session_state = SessionState([
            self.category_job, self.generator_job])
        # Select both of them for execution.
        self.session_state.update_desired_job_list([
            self.category_job, self.generator_job])
        # "execute" the "__category__" job by showing the session the result
        self.session_state.update_job_result(
            self.category_job, self.category_result)
        # Ensure that the generator job gained the "via" attribute
        # This is how we know the code above has no typos or anything.
        self.assertEqual(
            self.generator_job.via, self.category_job.get_checksum())
        # "execute" the "generator" job by showing the session the result.
        # Connect the 'on_job_added' signal to a helper function that
        # extracts the "generated" job

        def job_added(self, job):
            self.generated_job = job
        # Use partial to supply 'self' from the class into the function above
        self.session_state.on_job_added.connect(partial(job_added, self))
        # Show the result of the "generator" job to the session,
        # this will define the "generated" job, fire the signal
        # and call our callback
        self.session_state.update_job_result(
            self.generator_job, self.generator_result)
        # Ensure that we got the generated_job variable assigned
        # (by the event/signal handled above)
        self.assertIsNot(self.generated_job, None)
        # Now the stage is set for testing. Let's create the suspend helper
        # and use the data we've defined so far to create JSON-friendly
        # description of the session state.
        self.helper = SessionSuspendHelper1()
        self.data = self.helper._repr_SessionState(self.session_state)

    def test_state_tracked_for_all_jobs(self):
        """
        verify that 'state' keeps track of all three jobs
        """
        self.assertIn(self.category_job.name, self.data['jobs'])
        self.assertIn(self.generator_job.name, self.data['jobs'])
        self.assertIn(self.generated_job.name, self.data['jobs'])

    def test_category_job_result_is_saved(self):
        """
        verify that the 'category' job result was saved
        """
        # This result is essential to re-create the association
        # with the 'generator' job. In theory we could get it from
        # the 'via' attribute but that is only true for category assignment
        # where the child job already exists and is defined on the
        # filesystem. This would not work in the case of truly generated jobs
        # so for consistency it is done the same way.
        self.assertEqual(
            self.data['results']['__category__'], [{
                'comments': None,
                'execution_duration': None,
                'outcome': None,
                'return_code': None,
                'io_log': [
                    [0.0, 'stdout', 'cGx1Z2luOmxvY2FsCg=='],
                    [0.1, 'stdout', 'bmFtZTpnZW5lcmF0b3IK']
                ]
            }]
        )

    def test_generator_job_result_is_saved(self):
        """
        verify that the 'generator' job result was saved
        """
        self.assertEqual(
            self.data['results']['generator'], [{
                'comments': None,
                'execution_duration': None,
                'outcome': None,
                'return_code': None,
                'io_log': [
                    [0.0, 'stdout', 'bmFtZTpnZW5lcmF0ZWQ='],
                ]
            }]
        )

    def test_generated_job_result_is_saved(self):
        """
        verify that the 'generated' job result was saved
        """
        # This is the implicit "empty" result that all jobs have
        self.assertEqual(
            self.data['results']['generated'], [{
                'comments': None,
                'execution_duration': None,
                'outcome': None,
                'return_code': None,
                'io_log': []
            }]
        )

    def test_sanity_check(self):
        """
        verify that the whole suspend data looks right
        """
        # This test is pretty much a "eyeball" inspection test
        # where we can see everything at a glance and not have to
        # deduce how each part looks like from the tests above.
        #
        # All the data below is verbatim copy of the generated  suspend data
        # that was created when this test was written. The only modification
        # was wrapping of the checksums in ( ) to make them wrap correctly
        # so that the file can stay PEP-8 clean
        self.maxDiff = None
        self.assertEqual(self.data, {
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
        })


class SessionSuspendHelper2Tests(SessionSuspendHelper1Tests):
    """
    Tests for various methods of SessionSuspendHelper2
    """

    def setUp(self):
        self.helper = SessionSuspendHelper2()

    def test_json_repr_current_version(self):
        """
        verify what the version field is
        """
        data = self.helper._json_repr(SessionState([]))
        self.assertEqual(data['version'], 2)

    def test_repr_SessionMetaData_empty_metadata(self):
        """
        verify that representation of empty SessionMetaData is okay
        """
        # all defaults with empty values
        data = self.helper._repr_SessionMetaData(SessionMetaData())
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
        ))
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
        data = self.helper._repr_SessionState(SessionState([]))
        self.assertEqual(data, {
            'jobs': {},
            'results': {},
            'desired_job_list': [],
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
        data = self.helper.suspend(SessionState([]))
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
            b'{"session":{"desired_job_list":[],"jobs":{},"metadata":'
            b'{"app_blob":null,"flags":[],"running_job_name":null,"title":null'
            b'},"results":{}},"version":2}'))
