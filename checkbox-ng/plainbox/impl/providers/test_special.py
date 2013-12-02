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
plainbox.impl.providers.test_special
====================================

Test definitions for plainbox.impl.providers.special module
"""

from unittest import TestCase

from plainbox.impl.providers import ProviderNotFound
from plainbox.impl.providers.special import CheckBoxNotFound
from plainbox.impl.providers.special import CheckBoxSrcProvider
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor import mock


class CheckBoxSrcProviderTests(TestCase):

    def setUp(self):
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            self.provider = CheckBoxSrcProvider()

    @mock.patch('os.path.exists')
    def test_initializer_verifies_presence(self, mock_exists):
        """
        verify that CheckBoxNotFound is raised when working out-of-tree
        """
        mock_exists.return_value = False
        with self.assertRaises(CheckBoxNotFound) as boom:
            CheckBoxSrcProvider()
        self.assertIsInstance(boom.exception, ProviderNotFound)

    def test_extra_PYTHONPATH(self):
        """
        verify that extra_PYTHONPATH has a sane value
        """
        self.assertTrue(
            self.provider.extra_PYTHONPATH.endswith('checkbox-old'))


class TestCheckBox(TestCaseWithParameters):
    parameter_names = ('job',)

    @classmethod
    def get_parameter_values(cls):
        try:
            for job in CheckBoxSrcProvider().get_builtin_jobs():
                yield (job,)
        except ProviderNotFound:
            # This may happen if plainbox tests are invoked standalone,
            # without access to checkbox source tree
            pass

    def test_job_resource_expression(self):
        self.parameters.job.get_resource_program()
