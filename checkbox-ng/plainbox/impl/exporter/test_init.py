# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.exporter.test_init
================================

Test definitions for plainbox.impl.exporter module
"""

from collections import OrderedDict
from io import StringIO, BytesIO
from tempfile import TemporaryDirectory
from unittest import TestCase

from plainbox.abc import IJobResult
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.exporter import classproperty
from plainbox.impl.job import JobDefinition
from plainbox.impl.result import MemoryJobResult, IOLogRecord
from plainbox.impl.session import SessionState
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.testing_utils import make_job, make_job_result
from plainbox.impl.unit.category import CategoryUnit
from plainbox.vendor import mock


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

    def test_option_list_setting_boolean(self):
        exporter = self.TestSessionStateExporter()
        exporter._option_list = [
            SessionStateExporterBase.OPTION_WITH_IO_LOG,
            SessionStateExporterBase.OPTION_FLATTEN_IO_LOG]
        self.assertEqual(exporter._option_list, sorted([
            SessionStateExporterBase.OPTION_WITH_IO_LOG,
            SessionStateExporterBase.OPTION_FLATTEN_IO_LOG]))

    def test_option_list_setting_boolean_all_at_once(self):
        # Test every option set, all at once
        # Just to be paranoid, ensure the options I set are the ones the
        # exporter actually thinks it has
        exporter = self.TestSessionStateExporter(
            self.TestSessionStateExporter.supported_option_list)
        self.assertEqual(
            exporter._option_list,
            sorted(self.TestSessionStateExporter.supported_option_list))

    def test_option_list_init_non_boolean(self):
        option = SessionStateExporterBase.OPTION_WITH_COMMENTS
        exporter = self.TestSessionStateExporter(
            ["{}=detailed".format(option)])
        self.assertEqual(exporter.get_option_value(option), "detailed")

    def test_option_list_non_duplicated_options(self):
        # Setting the same option twice makes no sense, check it gets squashed
        # into only one item in the option_list.
        option = SessionStateExporterBase.OPTION_WITH_COMMENTS
        exporter = self.TestSessionStateExporter([option, option])
        self.assertEqual(exporter._option_list, [option])

    def test_option_list_setting_api(self):
        exporter = self.TestSessionStateExporter(
            [SessionStateExporterBase.OPTION_WITH_IO_LOG])
        exporter.set_option_value("with-comments")
        self.assertEqual(exporter.get_option_value('with-comments'), True)
        exporter.set_option_value("with-comments", "detailed")
        self.assertEqual(exporter.get_option_value('with-comments'),
                         "detailed")

    def test_defaults(self):
        # Test all defaults, with all options unset
        exporter = self.TestSessionStateExporter()
        session_manager = mock.Mock(spec_set=SessionManager,
                                    state=self.make_test_session())
        data = exporter.get_session_data_subset(session_manager)
        expected_data = {
            'result_map': {
                'job_a': OrderedDict([
                    ('summary', 'job_a'),
                    ('category_id', ('2013.com.canonical.plainbox::'
                                     'uncategorised')),
                    ('outcome', 'pass')
                ]),
                'job_b': OrderedDict([
                    ('summary', 'job_b'),
                    ('category_id', ('2013.com.canonical.plainbox::'
                                     'uncategorised')),
                    ('outcome', 'fail')
                ])
            }
        }
        self.assertEqual(data, expected_data)

    def make_realistic_test_session(self, session_dir):
        # Create a more realistic session with two jobs but with richer set
        # of data in the actual jobs and results.
        job_a = JobDefinition({
            'plugin': 'shell',
            'name': 'job_a',
            'summary': 'This is job A',
            'command': 'echo testing && true',
            'requires': 'job_b.ready == "yes"'
        })
        job_b = JobDefinition({
            'plugin': 'resource',
            'name': 'job_b',
            'summary': 'This is job B',
            'command': 'echo ready: yes'
        })
        session = SessionState([job_a, job_b])
        session.update_desired_job_list([job_a, job_b])
        result_a = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'return_code': 0,
            'io_log': [(0, 'stdout', b'testing\n')],
        })
        result_b = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'return_code': 0,
            'comments': 'foo',
            'io_log': [(0, 'stdout', b'ready: yes\n')],
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
            session_manager = mock.Mock(
                spec_set=SessionManager,
                state=self.make_realistic_test_session(scratch_dir))
            data = exporter.get_session_data_subset(session_manager)
        expected_data = {
            'job_list': ['job_a', 'job_b'],
            'run_list': ['job_b', 'job_a'],
            'desired_job_list': ['job_a', 'job_b'],
            'resource_map': {
                'job_b': [{
                    'ready': 'yes'
                }]
            },
            'category_map': {
                '2013.com.canonical.plainbox::uncategorised': 'Uncategorised'
            },
            'result_map': {
                'job_a': OrderedDict([
                    ('summary', 'This is job A'),
                    ('category_id', ('2013.com.canonical.plainbox::'
                                     'uncategorised')),
                    ('outcome', 'pass'),
                    ('comments', None),
                    ('via', None),
                    ('hash', '2def0c995e1b6d934c5a91286ba164'
                             '18845da26d057bc992a2b5dfeae2e2fe91'),
                    ('plugin', 'shell'),
                    ('requires', 'job_b.ready == "yes"'),
                    ('command', 'echo testing && true'),
                    ('io_log', ['dGVzdGluZwo=']),
                    ('certification_status', 'unspecified'),
                ]),
                'job_b': OrderedDict([
                    ('summary', 'This is job B'),
                    ('category_id', ('2013.com.canonical.plainbox::'
                                     'uncategorised')),
                    ('outcome', 'pass'),
                    ('comments', 'foo'),
                    ('via', None),
                    ('hash', 'ed19ba54624864a7c622ff7d1e8ed5'
                             '96b1a0fddc4b78c8fb780fe41e55250e6f'),
                    ('plugin', 'resource'),
                    ('command', 'echo ready: yes'),
                    ('io_log', ['cmVhZHk6IHllcwo=']),
                    ('certification_status', 'unspecified'),
                ])
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

    def test_category_map(self):
        """
        Ensure that passing OPTION_WITH_CATEGORY_MAP causes a category id ->
        tr_name mapping to show up.
        """
        exporter = self.TestSessionStateExporter([
            SessionStateExporterBase.OPTION_WITH_CATEGORY_MAP
        ])
        # Create three untis, two categories (foo, bar) and two jobs (froz,
        # bot) so that froz.category_id == foo
        cat_foo = CategoryUnit({
            'id': 'foo',
            'name': 'The foo category',
        })
        cat_bar = CategoryUnit({
            'id': 'bar',
            'name': 'The bar category',
        })
        job_froz = JobDefinition({
            'plugin': 'shell',
            'id': 'froz',
            'category_id': 'foo'
        })
        # Create and export a session with the three units
        state = SessionState([cat_foo, cat_bar, job_froz])
        session_manager = mock.Mock(spec_set=SessionManager, state=state)
        data = exporter.get_session_data_subset(session_manager)
        # Ensure that only the foo category was used, and the bar category was
        # discarded as nothing was referencing it
        self.assertEqual(data['category_map'], {
            'foo': 'The foo category',
        })

    def test_category_map_and_uncategorised(self):
        """
        Ensure that OPTION_WITH_CATEGORY_MAP synthetizes the special
        'uncategorised' category.
        """
        exporter = self.TestSessionStateExporter([
            SessionStateExporterBase.OPTION_WITH_CATEGORY_MAP
        ])
        # Create a job without a specific category
        job = JobDefinition({
            'plugin': 'shell',
            'id': 'id',
        })
        # Create and export a session with that one job
        state = SessionState([job])
        session_manager = mock.Mock(spec_set=SessionManager, state=state)
        data = exporter.get_session_data_subset(session_manager)
        # Ensure that the special 'uncategorized' category is used
        self.assertEqual(data['category_map'], {
            '2013.com.canonical.plainbox::uncategorised': 'Uncategorised',
        })


class ByteStringStreamTranslatorTests(TestCase):

    def test_smoke(self):
        dest_stream = StringIO()
        source_stream = BytesIO(b'This is a bytes literal')
        encoding = 'utf-8'

        translator = ByteStringStreamTranslator(dest_stream, encoding)
        translator.write(source_stream.getvalue())

        self.assertEqual('This is a bytes literal', dest_stream.getvalue())
