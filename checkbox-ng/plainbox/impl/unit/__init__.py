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
import jinja2

__all__ = ["get_accessed_parameters", "all_unit"]


def get_accessed_parameters(value, template_engine="default") -> frozenset:
    """
    Parse a new-style python string template and return parameter names

    :param value:
        Text string or value to parse
    :returns:
        A frozenset() with a list of names (or indices) of accessed parameters
    """
    to_r = []
    # for jinja templates, value will be a string if it contains jinja vars
    if isinstance(value, str):
        if template_engine == "jinja2":
            env = Environment()
            to_r = frozenset(
                    meta.find_undeclared_variables(env.parse(value))
                )
        elif template_engine == "default":
            # https://docs.python.org/3.4/library/string.html#string.Formatter.parse
            #
            # info[1] is the field_name (name of the referenced
            # formatting field) it _may_ be None if there are no format
            # parameters used
            to_r = [
                info[1]
                for info in string.Formatter().parse(value)
                if info[1] is not None
            ]
    elif isinstance(value, list):
        values = value
        for value in values:
            to_r += list(get_accessed_parameters(value, template_engine))
    elif isinstance(value, dict):
        # field + overrides
        assert len(value.keys()) == 1, "Somethings very wrong here"
        to_r += list(
            get_accessed_parameters(next(iter(value.keys())), template_engine)
        )

    return frozenset(to_r)


def get_array_field_qualify(field, field_name, qualifier, logger):
    """
    Compute and return a set of qualified ids from a variadic field.

    This implicitly parses the field if it is text (legacy pxu field or
    template) and then qualifies all the ids with the given qualifier
    """

    from plainbox.impl.xparsers import Visitor, WordList, Text, Error

    if field is None:
        return []

    to_ret = field

    if isinstance(field, str):
        to_ret = []

        class V(Visitor):

            def visit_Text_node(self, node: Text):
                to_ret.append(node.text)

            def visit_Error_node(self, node: Error):
                logger.warning("unable to parse %s: %s", field_name, node.msg)

        V().visit(WordList.parse(field))

    return list(map(qualifier, to_ret))


# Collection of all unit classes
all_units = PkgResourcesPlugInCollection("plainbox.unit")
