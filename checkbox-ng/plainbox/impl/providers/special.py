# This file is part of Checkbox.
#
# Copyright 2012, 2013, 2014 Canonical Ltd.
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
:mod:`plainbox.impl.providers.special` -- various special providers
===================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging
import os

from plainbox.i18n import gettext_noop as N_
from plainbox.impl import get_plainbox_dir
from plainbox.impl.secure.providers.v1 import Provider1
from plainbox.impl.secure.providers.v1 import Provider1Definition


logger = logging.getLogger("plainbox.providers.special")


def get_stubbox_def():
    """
    Get a Provider1Definition for stubbox
    """
    stubbox_def = Provider1Definition()
    stubbox_def.name = "2013.com.canonical.plainbox:stubbox"
    stubbox_def.version = "1.0"
    stubbox_def.description = N_("StubBox (dummy data for development)")
    stubbox_def.secure = False
    stubbox_def.gettext_domain = "stubbox"
    stubbox_def.location = os.path.join(
        get_plainbox_dir(), "impl/providers/stubbox")
    return stubbox_def


def get_stubbox():
    return Provider1.from_definition(get_stubbox_def(), secure=False)


def get_categories_def():
    """
    Get a Provider1Definition for the provider that knows all the categories
    """
    categories_def = Provider1Definition()
    categories_def.name = "2013.com.canonical.plainbox:categories"
    categories_def.version = "1.0"
    categories_def.description = N_("Common test category definitions")
    categories_def.secure = False
    categories_def.gettext_domain = "2013_com_canonical_plainbox_categories"
    categories_def.location = os.path.join(
        get_plainbox_dir(), "impl/providers/categories")
    return categories_def


def get_categories():
    return Provider1.from_definition(get_categories_def(), secure=False)
