# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
:mod:`plainbox.i18n` -- i18n support
====================================

This module provides public APIs for plainbox translation system. Currently
all functions exported here are STUB and offer no translations. In addition,
functions defined in this module are assumed to implicitly use the gettext
domain ``"plainbox"``.
"""


def gettext(msgid):
    """
    no-op gettext implementation
    """
    return msgid


def ngettext(msgid1, msgid2, n):
    """
    no-op ngettext implementation
    """
    if n == 1:
        return msgid1
    else:
        return msgid2
