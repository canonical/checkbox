# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.exporter.test_init
================================

Test definitions for plainbox.impl.exporter module
"""

from io import StringIO, BytesIO
from tempfile import TemporaryDirectory
from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.exporter import classproperty
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import JobResult, IOLogRecord
from plainbox.impl.session import SessionState
from plainbox.impl.testing_utils import make_io_log, make_job, make_job_result


class ClassPropertyTests(TestCase):

    def get_C(self):

        class C:
            attr = "data"

            @classproperty
            def prop(cls):
                return cls.attr

        return C

    def test_classproperty_on_cls(self):
        cls = self.get_C()
        self.assertEqual(cls.prop, cls.attr)

    def test_classproperty_on_obj(self):
        cls = self.get_C()
        obj = cls()
        self.assertEqual(obj.prop, obj.attr)


class SessionStateExporterBaseTests(TestCase):

    class TestSessionStateExporter(SessionStateExporterBase):

        def dump(self, data, stream):
            """
            Dummy implementation of a method required by the base class.
            """

    def make_test_session(self):
        # Create a small session with two jobs and two results
        job_a = make_job('job_a')
        job_b = make_job('job_b')
        session = SessionState([job_a, job_b])
        session.update_desired_job_list([job_a, job_b])
        result_a = make_job_result(outcome=IJobResult.OUTCOME_PASS)
        result_b = make_job_result(outcome=IJobResult.OUTCOME_FAIL)
        session.update_job_result(job_a, result_a)
        session.update_job_result(job_b, result_b)
        return session

    def test_defaults(self):
        # Test all defaults, with all options unset
        exporter = self.TestSessionStateExporter()
        session = self.make_test_session()
        data = exporter.get_session_data_subset(session)
        expected_data = {
            'result_map': {
                'job_a': {
                    'outcome': 'pass'
                },
                'job_b': {
                    'outcome': 'fail'
                }
            }
        }
        self.assertEqual(data, expected_data)

    def make_realistic_test_session(self, session_dir):
        # Create a more realistic session with two jobs but with richer set
        # of data in the actual jobs and results.
        job_a = JobDefinition({
            'plugin': 'shell',
            'name': 'job_a',
            'command': 'echo testing && true',
            'requires': 'job_b.ready == "yes"'
        })
        job_b = JobDefinition({
            'plugin': 'resource',
            'name': 'job_b',
            'command': 'echo ready: yes'
        })
        session = SessionState([job_a, job_b])
        session.update_desired_job_list([job_a, job_b])
        result_a = JobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'return_code': 0,
            'io_log': make_io_log(
                (IOLogRecord(0, 'stdout', b'testing\n'),),
                session_dir)
        })
        result_b = JobResult({
            'outcome': 'pass',
            'outcome': IJobResult.OUTCOME_PASS,
            'return_code': 0,
            'comments': 'foo',
            'io_log': make_io_log(
                (IOLogRecord(0, 'stdout', b'ready: yes\n'),),
                session_dir)
        })
        session.update_job_result(job_a, result_a)
        session.update_job_result(job_b, result_b)
        return session

    def test_all_at_once(self):
        # Test every option set, all at once
        # Currently this sets both OPTION_WITH_IO_LOG and
        # one of the two mutually exclusive options:
        #   - OPTION_SQUASH_IO_LOG
        #   - OPTION_FLATTEN_IO_LOG
        # The implementation favours SQUASH_IO_LOG
        # and thus the code below tests that option
        with TemporaryDirectory() as scratch_dir:
            exporter = self.TestSessionStateExporter(
                self.TestSessionStateExporter.supported_option_list)
            session = self.make_realistic_test_session(scratch_dir)
            data = exporter.get_session_data_subset(session)
        expected_data = {
            'job_list': ['job_a', 'job_b'],
            'run_list': ['job_b', 'job_a'],
            'desired_job_list': ['job_a', 'job_b'],
            'resource_map': {
                'job_b': [{
                    'ready': 'yes'
                }]
            },
            'result_map': {
                'job_a': {
                    'outcome': 'pass',
                    'plugin': 'shell',
                    'command': 'echo testing && true',
                    'io_log': ['dGVzdGluZwo='],
                    'requires': 'job_b.ready == "yes"',
                    'comments': None,
                    'via': None,
                    'hash': '1dbae753f6cb823af370ef9fcb5916'
                            'eba82185992e81813316fe77332a60f1e0',
                },
                'job_b': {
                    'outcome': 'pass',
                    'plugin': 'resource',
                    'command': 'echo ready: yes',
                    'io_log': ['cmVhZHk6IHllcwo='],
                    'comments': 'foo',
                    'via': None,
                    'hash': 'a914c7396e29c2a4669055bf38bd7c'
                            '7f0eae0bc67f8bc2d90ba7d37f83e52132',
                }
            },
            'attachment_map': {
            }
        }
        # This is just to make debugging easier
        self.assertEqual(expected_data.keys(), data.keys())
        for key in data.keys():
            self.assertEqual(expected_data[key], data[key],
                             msg="wrong data in %r" % key)
        # This is to make sure we didn't miss anything by being too smart
        self.assertEqual(data, expected_data)

    def test_io_log_processors(self):
        # Test all of the io_log processors that are built into
        # the base SessionStateExporter class
        cls = self.TestSessionStateExporter
        io_log = (
            IOLogRecord(0, 'stdout', b'foo\n'),
            IOLogRecord(1, 'stderr', b'bar\n'),
            IOLogRecord(2, 'stdout', b'quxx\n')
        )
        self.assertEqual(
            cls._squash_io_log(io_log), [
                'Zm9vCg==', 'YmFyCg==', 'cXV4eAo='])
        self.assertEqual(
            cls._flatten_io_log(io_log),
            'Zm9vCmJhcgpxdXh4Cg==')
        self.assertEqual(
            cls._io_log(io_log), [
                (0, 'stdout', 'Zm9vCg=='),
                (1, 'stderr', 'YmFyCg=='),
                (2, 'stdout', 'cXV4eAo=')])


class ByteStringStreamTranslatorTests(TestCase):

    def test_smoke(self):
        dest_stream = StringIO()
        source_stream = BytesIO(b'This is a bytes literal')
        encoding = 'utf-8'

        translator = ByteStringStreamTranslator(dest_stream, encoding)
        translator.write(source_stream.getvalue())

        self.assertEqual('This is a bytes literal', dest_stream.getvalue())
