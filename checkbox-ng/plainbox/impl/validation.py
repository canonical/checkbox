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
import copy

from plainbox.i18n import gettext as _
from plainbox.i18n import gettext_noop as N_
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
    unknown_param = 'unknown_param'
    syntax_error = 'syntax_error'
    unknown = 'unknown'
    not_unique = 'not_unique'
    expected_i18n = 'expected_i18n'
    unexpected_i18n = 'unexpected_i18n'
    bad_reference = 'bad_reference'


class Severity(SymbolDef, allow_outer={"N_"}):
    """
    Symbols for class:`Issue` severity
    """
    error = N_('error')
    warning = N_('warning')
    advice = N_('advice')


class Issue:
    """
    Base carrier class for information about problems

    :attr message:
        Short description of the problem (one line)
    :attr severity:
        Severity of the problem (see :class:`Severity`)
    :attr kind:
        Problem "type" which is a Symbol with ``errno``-like semantics
    :attr origin:
        (optional) Origin of the problem
        (see :class:`plainbox.impl.secure.origin.Origin`)
    """

    def __init__(self, message, severity, kind, origin):
        self.message = message
        self.severity = severity
        self.kind = kind
        self.origin = origin

    def __str__(self):
        if self.origin is not None:
            return "{origin}: {severity}: {message}".format(
                origin=self.origin, severity=_(str(self.severity)),
                message=self.message)
        else:
            return "{severity}: {message}".format(
                severity=_(str(self.severity)), message=self.message)

    def __repr__(self):
        return (
            "{}(message={!r}, severity={!r}, kind={!r}, origin={!r})"
        ).format(self.__class__.__name__, self.message,
                 self.severity, self.kind, self.origin)

    def relative_to(self, base_dir):
        other = copy.copy(self)
        if self.origin is not None:
            other.origin = self.origin.relative_to(base_dir)
        return other


class ValidationError(ValueError):
    """
    Exception raised by to report jobs with problematic definitions.
    """

    def __init__(self, field, problem, hint=None, origin=None):
        self.field = field
        self.problem = problem
        self.hint = hint
        self.origin = origin

    def __str__(self):
        return _("Problem with field {}: {}").format(self.field, self.problem)

    def __repr__(self):
        return (
            "ValidationError(field={!r}, problem={!r}, "
            "hint={!r}, origin={!r})"
        ).format(self.field, self.problem, self.hint, self.origin)
