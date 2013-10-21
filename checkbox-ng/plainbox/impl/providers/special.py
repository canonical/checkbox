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
:mod:`plainbox.impl.providers.special` -- various special providers
===================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging
import os

from plainbox.impl import get_plainbox_dir
from plainbox.impl.providers import ProviderNotFound
from plainbox.impl.providers.v1 import Provider1


logger = logging.getLogger("plainbox.providers.special")


class CheckBoxNotFound(ProviderNotFound):
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

    Unlike normal v1 providers it has two legacy quirks that should not be
    changed before we can stop using the old checkbox codebase.

    1) The location for provider-specific executables is '$base/scripts'. This
       is implemented by custom :attr:`extra_PATH` and :attr:`scripts_dir`.

    2) The location for whitelists is '$base/data/whitelists'. This is
       implemented by custom :attr:`whitelists_dir`.

    It also has some quirks which might be revisited and dropped:

    1) To ensure that old checkbox library codebase can be imported (whitout
       installing or developing checkbox) it implements
       :attr:`extra_PYTHONPATH`.

    2) It has an utility method called :meth:`exists()` that makes one piece of
       code shorter (save the time it takes to create CheckBoxSrcProvider and
       catch-ignore ProviderNotFound).
    """

    def __init__(self):
        super(CheckBoxSrcProvider, self).__init__(
            _get_checkbox_dir(),
            "2013.com.canonical:checkbox-src",
            "CheckBox (live source)", False)
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

    @property
    def whitelists_dir(self):
        """
        Return an absolute path of the whitelist directory
        """
        return os.path.join(self._base_dir, "data", "whitelists")

    @property
    def scripts_dir(self):
        """
        Return an absolute path of the scripts directory

        .. note::
            The scripts may not work without setting PYTHONPATH and
            CHECKBOX_SHARE.
        """
        return os.path.join(self._base_dir, "scripts")

    @property
    def extra_PATH(self):
        """
        Return additional entry for PATH

        This entry is required to lookup CheckBox scripts.
        """
        return self.scripts_dir


class StubBoxProvider(Provider1):
    """
    A provider for stub, dummy and otherwise non-production jobs.

    The stubbox provider is useful for various kinds of testing where you don't
    want to pull in a volume of data, just a bit of each kind of jobs that we
    need to support.
    """

    def __init__(self):
        super(StubBoxProvider, self).__init__(
            os.path.join(get_plainbox_dir(), "impl/providers/stubbox"),
            "2013.com.canonical:stubbox",
            "StubBox (dummy data for development)", False)
