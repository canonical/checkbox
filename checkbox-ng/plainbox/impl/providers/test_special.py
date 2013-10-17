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
plainbox.impl.providers.test_special
====================================

Test definitions for plainbox.impl.providers.special module
"""

from plainbox.impl.providers.special import CheckBoxSrcProvider
from plainbox.testing_utils.testcases import TestCaseWithParameters


class TestCheckBox(TestCaseWithParameters):
    parameter_names = ('job',)

    @classmethod
    def get_parameter_values(cls):
        for job in CheckBoxSrcProvider().get_builtin_jobs():
            yield (job,)

    def test_job_resource_expression(self):
        self.parameters.job.get_resource_program()
