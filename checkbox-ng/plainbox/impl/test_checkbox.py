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
plainbox.impl.test_checkbox
===========================

Test definitions for plainbox.impl.checkbox module
"""

from contextlib import contextmanager
from io import TextIOWrapper
from unittest import TestCase

import mock

from plainbox.impl.checkbox import CheckBox, WhiteList
from plainbox.impl.testing_utils import make_job
from plainbox.testing_utils.testcases import TestCaseWithParameters


class WhiteListTests(TestCase):

    _name = 'whitelist.txt'

    _content = [
        "# this is a comment",
        "foo # this is another comment",
        "bar",
        ""
    ]

    @contextmanager
    def mocked_file(self, name, content):
        m_open = mock.MagicMock(name='open', spec=open)
        m_stream = mock.MagicMock(spec=TextIOWrapper)
        m_stream.__enter__.return_value = m_stream
        m_stream.__iter__.side_effect = lambda: iter(content)
        m_open.return_value = m_stream
        with mock.patch('plainbox.impl.checkbox.open', m_open, create=True):
            yield
        m_open.assert_called_once_with(name, "rt", encoding="UTF-8")

    def test_load_patterns(self):
        with self.mocked_file(self._name, self._content):
            pattern_list = WhiteList._load_patterns(self._name)
        self.assertEqual(pattern_list, ['^foo$', '^bar$'])

    def test_smoke(self):
        with self.mocked_file(self._name, self._content):
            whitelist = WhiteList.from_file(self._name)
        self.assertEqual(
            repr(whitelist.inclusive_qualifier_list[0]),
            "<RegExpJobQualifier pattern:'^foo$'>")
        self.assertTrue(whitelist.designates(make_job('foo')))


class TestCheckBox(TestCaseWithParameters):
    parameter_names = ('job',)

    @classmethod
    def get_parameter_values(cls):
        for job in CheckBox().get_builtin_jobs():
            yield (job,)

    def test_job_resource_expression(self):
        self.parameters.job.get_resource_program()
