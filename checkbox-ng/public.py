# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
plainbox.public
===============

Public, high-level API for third party developers.

The are actually implemented by the plainbox.impl package. This module is here
so that the essential API concepts are in a single spot and are easier to
understand (by not being mixed with additional source code).

.. note::

    This module has API stability guarantees. We are not going to break or
    introduce backwards incompatible interfaces here without following our API
    deprecation policy. All existing features will be retained for at least
    three releases. All deprecated symbols will warn when they will cease to be
    available.
"""

from plainbox.impl import public


@public('plainbox.impl.utils')
def get_builtin_test_definitions():
    """
    Get all the test definitions that are built into checkbox
    """


@public('plainbox.impl.utils')
def save(something, somewhere):
    """
    Save something somewhere

    The ultimate high-level serialization interface.

    Something can be a TestDefinition or a TestResult object.
    Somewhere may be a file-like object or a filename.
    """


@public('plainbox.impl.utils')
def load(somewhere):
    """
    Load some something from somewhere!

    The ultimate high-level deserialization interface

    Somewhere may be a file-like object or a filename.
    The returned something is a TestDefinition or a TestResult.
    """
    # XXX: should we handle basic collections at this level - as in, many test
    # {definitions,results} in one file. If so can we just return a list.


@public('plainbox.impl.utils')
def run(*args, **kwargs):
    """
    Run checkbox tests!

    The ultimate high-level execution, er, interface.

    This is the best way to create customized checkbox-based solutions that
    need to perform custom manipulation beyond the scope of the core checkbox
    use cases supported by the canonical hardware certification team.

    Positional arguments:

        When no positional arguments are provided checkbox will behave as if
        called with get_builtin_test_definitions()

        Each positional argument is handled separately depending on the type:

            string:

                Each string is converted to a pattern that tries to match the
                name property of the tests built into checkbox (which are
                returned by get_builtin_test_definitions).

            TestDefinition:

                Checkbox will run that test directly

    Keyword arguments:

        ui:
            Selects the user interface presented to the user. Available options
            are 'headless', 'text', 'graphics' (which selects the best UI for
            the current system) or a custom UI object (advanced topic). When
            not provided a default user interface, appropriate for the local
            system, is selected (text mode if headless).

            NOTE: Headless mode is the only non-interactive mode available! All
            other modes will require you to provide some user interaction in
            certain tests.

        intro_page:
            Specifies the custom "intro" page to display. This can be used to
            create vendor-specific certification programs with great ease. The
            format is is restructured text which will be either displayed as-is
            in text user interface or rendered appropriately by graphical user
            interface.

        outro_page:
            Specifies the custom "outro" page to display. It will be displayed
            before calling the on_done() handler so that it can display
            appropriate message to the user. An "exit" button will be presented
            and made active once the on_done handler finishes. For standard
            handlers (send-to-certification, send-to-hexer, save-to-file) an
            appropriate UI will be automatically presented.

        on_done:
            Specifies what to do when the whole test run is complete. Can be a
            plain string like "send-to-certification" (default) "send-to-hexer"
            and "save-to-file" or a function that gets called with a list of
            results, such as lambda results: print(results)
    """


@public('plainbox.impl.main')
def main(argv=None):
    """
    Entry point for the temporary new plainbox
    """
