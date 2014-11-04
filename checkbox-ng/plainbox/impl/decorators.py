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
:mod:`plainbox.impl.decorators` -- utility decorators
=====================================================
"""
import functools
import logging

__all__ = ['raises']

_bug_logger = logging.getLogger("plainbox.bug")


class UndocumentedException(TypeError):
    """
    Exception raised when an exception declared in ``@raises()`` is
    not documented in the docstring of the decorated function that
    otherwise has a docstring.

    :attr exc_cls:
        The exception class that is not documented
    :attr func:
        The function that is lacking documentation
    """

    def __init__(self, func, exc_cls):
        self.func = func
        self.exc_cls = exc_cls

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.exc_cls)

    def __str__(self):
        return (
            "{!r} (from {!a}:{:d}) doesn't document possible"
            " exception: {!r}"
        ).format(
            self.func,
            self.func.__code__.co_filename,
            self.func.__code__.co_firstlineno,
            self.exc_cls.__name__)


def raises(*exc_cls_list: Exception):
    """
    Declare possible exceptions from a callable

    :param exc_cls_list:
        A list of exceptions that may be raised
    :returns:
        A decorator that applies the following transformations
    :raises TypeError:
        If any of the exceptions listed aren't subclasses of ``Exception``
    :raises UndocumentedException:
        If the decorated function has a docstring but doesn't document all the
        exceptions listed in ``exc_cls_list``. Note that for undocumented
        functions this will simply do nothing at all.

    1) The original function is wrapped with a helper that detects
       undeclared exceptions and issues an appropriate message on the
       "plainbox.bug" logger. The intent is to fix documentation and/or
       error handling so that cases like that don't happen.
    2) The wrapper function is modified so that __annotations__ gains the
       'raise' annotation (mimicking the 'return' annotation for returned
       valued) which contains the list of exceptions that may be raised.
    """
    for exc_cls in exc_cls_list:
        if not isinstance(exc_cls, type) or not issubclass(exc_cls, Exception):
            raise TypeError("All arguments must be exceptions")

    def decorator(func):
        # Enforce documentation of all the exceptions
        if func.__doc__ is not None:
            for exc_cls in exc_cls_list:
                if ':raises {}:'.format(exc_cls.__name__) not in func.__doc__:
                    raise UndocumentedException(func, exc_cls)

        # Wrap in detector function
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if not isinstance(exc, exc_cls_list):
                    _bug_logger.error(
                        "Undeclared exception %s raised from %s",
                        exc.__class__.__name__, func.__name__)
                raise exc
        # Annotate the function and the wrapper
        wrapper.__annotations__['raise'] = exc_cls_list
        func.__annotations__['raise'] = exc_cls_list
        return wrapper
    return decorator

# Annotate thyself
raises = raises(TypeError)(raises)
