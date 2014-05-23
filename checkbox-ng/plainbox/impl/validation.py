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
:mod:`plainbox.impl.validation` -- validation tools
===================================================
"""

import logging

from plainbox.i18n import gettext as _
from plainbox.impl.symbol import SymbolDef


logger = logging.getLogger("plainbox.validation")


class Problem(SymbolDef):
    """
    Symbols for each possible problem that a field value may have
    """
    missing = 'missing'
    wrong = 'wrong'
    useless = 'useless'
    deprecated = 'deprecated'
    constant = 'constant'
    variable = 'variable'


class ValidationError(ValueError):
    """
    Exception raised by to report jobs with problematic definitions.
    """

    def __init__(self, field, problem, hint=None):
        self.field = field
        self.problem = problem
        self.hint = hint

    def __str__(self):
        return _("Problem with field {}: {}").format(self.field, self.problem)

    def __repr__(self):
        if self.hint is None:
            return "ValidationError(field={!r}, problem={!r})".format(
                self.field, self.problem)
        else:
            return (
                "ValidationError(field={!r}, problem={!r}, "
                "hint={!r})"
            ).format(self.field, self.problem, self.hint)
