# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.unit.job` -- job unit
=========================================
"""

import re

from . import Unit


class BaseJob(Unit):
    """
    Base Job definition class.
    """

    def __init__(self, data, raw_data=None):
        """
        Initialize a new BaseJob object

        :param data:
            A dictionary of normalized data.

            This data is suitable for normal application usage. It is not
            suitable for gettext lookups as the original form is lost by the
            normalization process.

        :param raw_data:
            A dictionary of raw data (optional). Defaults to data.

            Data in this dictionary is in its raw form, as it was written in a
            job definition file. This data is suitable for gettext lookups.
        """
        super().__init__(data, raw_data=raw_data)

    @property
    def plugin(self):
        return self.get_record_value('plugin')

    @property
    def command(self):
        return self.get_record_value('command')

    @property
    def environ(self):
        return self.get_record_value('environ')

    @property
    def user(self):
        return self.get_record_value('user')

    @property
    def shell(self):
        """
        Shell that is used to interpret the command

        Defaults to 'bash' for checkbox compatibility.
        """
        return self.get_record_value('shell', 'bash')

    def get_environ_settings(self):
        """
        Return a set of requested environment variables
        """
        if self.environ is not None:
            return {variable for variable in re.split('[\s,]+', self.environ)}
        else:
            return set()
