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
:mod:`plainbox.impl.unit` -- package with all of the units
==========================================================
"""

import string

from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection

from jinja2 import Environment, meta

__all__ = ['get_accessed_parameters', 'all_unit']


def get_accessed_parameters(text, template_engine='default'):
    """
    Parse a new-style python string template and return parameter names

    :param text:
        Text string to parse
    :returns:
        A frozenset() with a list of names (or indices) of accessed parameters
    """
    if template_engine == 'jinja2':
        env = Environment()
        return frozenset(meta.find_undeclared_variables(env.parse(text)))
    else:
    # https://docs.python.org/3.4/library/string.html#string.Formatter.parse
    #
    # info[1] is the field_name (name of the referenced
    # formatting field) it _may_ be None if there are no format
    # parameters used
        return frozenset(
            info[1] for info in string.Formatter().parse(text)
            if info[1] is not None)


# Collection of all unit classes
all_units = PkgResourcesPlugInCollection('plainbox.unit')
