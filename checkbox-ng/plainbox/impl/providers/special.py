# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.providers.special` -- Implementation of special providers
=============================================================================
"""

import logging

from plainbox.abc import IProvider1, IProviderBackend1
from plainbox.impl.providers.checkbox import CheckBoxAutoProvider


logger = logging.getLogger("plainbox.providers.special")


class IHVProvider(IProvider1, IProviderBackend1):

    def __init__(self, real=None):
        if real is None:
            real = CheckBoxAutoProvider()
        self._real = real

    @property
    def name(self):
        return "ihv"

    @property
    def description(self):
        return "IHV"

    def get_builtin_jobs(self):
        # XXX: should we filter jobs too?
        return self._real.get_builtin_jobs()

    def get_builtin_whitelists(self):
        return [
            whitelist
            for whitelist in self._real.get_builtin_whitelists()
            if whitelist.name.startswith('ihv-')]

    @property
    def CHECKBOX_SHARE(self):
        return self._real.CHECKBOX_SHARE

    @property
    def extra_PYTHONPATH(self):
        return self._real.extra_PYTHONPATH

    @property
    def extra_PATH(self):
        return self._real.extra_PATH
