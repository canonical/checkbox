# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.unit_with_id` -- unit with identifier definition
====================================================================
"""

import logging

from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit._legacy import UnitWithIdLegacyAPI

__all__ = ['UnitWithId']


logger = logging.getLogger("plainbox.unit")


class UnitWithId(Unit, UnitWithIdLegacyAPI):
    """
    Base class for Units that have unique identifiers

    Unlike the JobDefintion class thepartial_id property has no fallback
    and is simply tied directly to the "id" field. The id property works
    in conjunction with a provider associated with the unit and simply adds
    the namespace part.
    """

    @property
    def partial_id(self):
        """
        Identifier of this category, without the provider name
        """
        return self.get_record_value('id')

    @property
    def id(self):
        if self.provider:
            return "{}::{}".format(self.provider.namespace, self.partial_id)
        else:
            return self.partial_id
