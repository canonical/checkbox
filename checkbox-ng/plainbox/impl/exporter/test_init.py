# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
plainbox.impl.exporter.test_init
================================

Test definitions for plainbox.impl.exporter module
"""

from unittest import TestCase

from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.exporter import classproperty
from plainbox.impl.session import SessionState
from plainbox.impl.testing_utils import make_job, make_job_result


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
        result_a = make_job_result(job_a, 'pass')
        result_b = make_job_result(job_b, 'fail')
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
