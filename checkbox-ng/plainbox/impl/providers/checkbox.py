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
:mod:`plainbox.impl.providers.checkbox` -- CheckBox Provider
============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging
import os

from plainbox.impl import get_plainbox_dir
from plainbox.impl.providers.v1 import Provider1


logger = logging.getLogger("plainbox.providers.checkbox")


class CheckBoxNotFound(LookupError):
    """
    Exception used to report that CheckBox cannot be located
    """

    def __repr__(self):
        return "CheckBoxNotFound()"

    def __str__(self):
        return "CheckBox cannot be found"


def _get_checkbox_dir():
    """
    Return the root directory of the checkbox source checkout

    Historically plainbox used a git submodule with checkbox tree (converted to
    git). This ended with the merge of plainbox into the checkbox tree.

    Now it's the other way around and the checkbox tree can be located two
    directories "up" from the plainbox module, in a checkbox-old directory.
    """
    return os.path.normpath(
        os.path.join(
            get_plainbox_dir(), "..", "..", "checkbox-old"))


class CheckBoxSrcProvider(Provider1):
    """
    A provider for checkbox jobs when used in development mode.

    This provider is only likely to be used when developing checkbox inside a
    virtualenv environment. It assumes the particular layout of code and data
    (relative to the code directory) directories.
    """

    def __init__(self):
        super(CheckBoxSrcProvider, self).__init__(
            _get_checkbox_dir(),
            "2013.com.canonical:checkbox-src",
            "CheckBox (live source)")
        if not os.path.exists(self._base_dir):
            raise CheckBoxNotFound()

    @staticmethod
    def exists():
        """
        Check if the source provider exists and can be actually used
        """
        return os.path.exists(_get_checkbox_dir())

    @property
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.
        """
        # NOTE: When CheckBox is installed then all the scripts should not use
        # 'env' to locate the python interpreter (otherwise they might use
        # virtualenv which is not desirable for Debian packages). When we're
        # using CheckBox from source then the source directory (which contains
        # the 'checkbox' package) should be added to PYTHONPATH for all the
        # imports to work.
        return _get_checkbox_dir()
