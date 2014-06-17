# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
:mod:`plainbox.impl` -- implementation package
==============================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
from functools import wraps
from inspect import getabsfile
from warnings import warn
import os.path
import sys
import textwrap

import plainbox
from plainbox.impl._textwrap import _textwrap_indent


def _get_doc_margin(doc):
    """
    Find minimum indentation of any non-blank lines after first line.
    """
    lines = doc.expandtabs().split('\n')
    margin = sys.maxsize
    for line in lines[1:]:
        content = len(line.lstrip())
        if content:
            indent = len(line) - content
            margin = min(margin, indent)
    return 0 if margin == sys.maxsize else margin


def public(import_path, introduced=None, deprecated=None):
    """
    Public API decorator generator.

    This decorator serves multiple uses:

        * It clearly documents all public APIs. This is visible to
          both developers reading the source code directly and to people
          reading code documentation (by adjusting __doc__)

        * It provides a stable import location while allowing to move the
          implementation around as the code evolves. This unbinds the name and
          documentation of the symbol from the code.

        * It documents when each function was introduced. This is also visible
          in the generated documentation.

        * It documents when each function will be decommissioned. This is
          visible in the generated documentation and at runtime. Each initial
          call to a deprecated function will cause a PendingDeprecationWarnings
          to be logged.

    The actual implementation of the function must be in in a module specified
    by import_path. It can be a module name or a module name and a function
    name, when separated by a colon.
    """
    # Create a forwarding decorator for the shim fuction The shim argument is
    # the actual empty function from the public module that serves as
    # documentation carrier.
    def decorator(shim):
        # Allow to override function name by specifying it in the import path
        # after a colon. If missing it defaults to the name of the shim
        try:
            module_name, func_name = import_path.split(":", 1)
        except ValueError:
            module_name, func_name = import_path, shim.__name__
        # Import the module with the implementation and extract the function
        module = __import__(module_name, fromlist=[''])
        try:
            impl = getattr(module, func_name)
        except AttributeError:
            raise NotImplementedError(
                "%s.%s does not exist" % (module_name, func_name))

        @wraps(shim)
        def call_impl(*args, **kwargs):
            return impl(*args, **kwargs)
        # Document the public nature of the function
        call_impl.__doc__ += "\n".join([
            "",
            "    This function is a part of the public API",
            "    The private implementation is in {}:{}".format(
                import_path, shim.__name__)
        ])
        if introduced is None:
            call_impl.__doc__ += "\n".join([
                "",
                "    This function was introduced in the initial version of"
                " plainbox",
            ])
        else:
            call_impl.__doc__ += "\n".join([
                "",
                "    This function was introduced in version: {}".format(
                    introduced)
            ])
        # Document deprecation status, if any
        if deprecated is not None:
            call_impl.__doc__ += "\n".join([
                "    warn:",
                "        This function is deprecated",
                "        It will be removed in version: {}".format(deprecated),
            ])
        # Add implementation docs, if any
        if impl.__doc__ is not None:
            call_impl.__doc__ += "\n".join([
                "    Additional documentation from the private"
                " implementation:"])
            call_impl.__doc__ += impl.__doc__
        return call_impl
    return decorator


def deprecated(version, explanation=None):
    """
    Decorator for marking functions as deprecated

    :param version:
        Version in which a function is deprecated
    :param explanation:
        Explanation of the deprecation. Ideally this will include hints on how
        to get a modern replacement.

    Deprecated functions are candidates for removal. Existing code should be
    adapted not to make any calls to the deprecated functions. New code should
    not use such functions.

    ..note::
        Due to the way python warning module works, to see deprecated function
        notices re-run your application with PYTHONWARNINGS=once
    """
    if not isinstance(version, str):
        # Due to a common mistake, 'version' is probably the decorated function
        # and @deprecated was called without ()
        raise SyntaxError("@deprecated() must be called with a parameter")

    def decorator(func):
        """
        The @deprecated decorator with deprecation information
        """
        msg = "{0} is deprecated since version {1}".format(
            func.__name__, version)
        if func.__doc__ is None:
            func.__doc__ = ''
            indent = 4 * ' '
        else:
            indent = _get_doc_margin(func.__doc__) * ' '
            func.__doc__ += indent + '\n'
        func.__doc__ += indent + '.. deprecated:: {}'.format(version)
        if explanation is not None:
            func.__doc__ += _textwrap_indent(
                textwrap.dedent(explanation), prefix=indent * 2)

        @wraps(func)
        def wrapper(*args, **kwargs):
            warn(DeprecationWarning(msg), stacklevel=2)
            return func(*args, **kwargs)
        return wrapper

    return decorator


def get_plainbox_dir():
    """
    Return the root directory of the plainbox package.
    """
    return os.path.dirname(getabsfile(plainbox))
