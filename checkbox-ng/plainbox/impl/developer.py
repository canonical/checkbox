# This file is part of Checkbox.
#
# Copyright 2015-2026 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

"""Support code for enforcing usage expectations on public API."""

from collections import deque
from collections.abc import Callable

import sys

if sys.version_info < (3, 9):
    from typing import Dict
else:
    Dict = dict

__all__ = ("UsageExpectation",)

MODIFICATION_HISTORY = 5

_msg_template = """
Uh, oh...

If you see this message then there is a bug somewhere in Checkbox. We are
sorry for this. Please report this to us.

You are not expected to call {cls_name}.{fn_name} at this time.
The set of allowed calls, at this time, is:

{allowed_calls}

The last {modification_size} modifications were done by (most recent last):

{modification_history}
"""


class UnexpectedMethodCall(Exception):
    """
    Developer error reported when an unexpected method call is made.

    This type of error is reported when some set of methods is expected to be
    called in a given way but that expectation was not followed.
    """

    def __init__(self, cls, fn_name, allowed_pairs, history):
        """
        Initialize a new exception.

        :param cls:
            The class this exception refers to (the code user calls must be a
            method on that class).
        :param fn_name:
            Name of the method that was unexpectedly called.
        :param allowed_pairs:
            A sequence of pairs ``(fn_name, why)`` that explain the set of
            allowed function calls. There is a certain pattern on how the
            ``why`` strings are expected to be structured. They will be used as
            a part of a string that looks like this: ``' - call {fn_name}() to
            {why}.'``. Developers should use explanations that look natural in
            this context. This text is not meant for internationalization.
        :param history:
            A sequence of functions that modified the allowed_pairs and how
            they did so (fn_name, action), where action is "allow", "disallow",
            "allow_all_clear", "allow_all_no_clear"
        """
        self.cls = cls
        self.fn_name = fn_name
        self.allowed_pairs = allowed_pairs
        self.history = history

    def __str__(self):
        """Get a developer-friendly message that describes the problem."""
        return _msg_template.format(
            cls_name=self.cls.__name__,
            fn_name=self.fn_name,
            allowed_calls="\n".join(
                " - call {}.{}() to {}.".format(
                    self.cls.__name__, allowed_fn_name, why
                )
                for allowed_fn_name, why in self.allowed_pairs
            ),
            modification_history=" - "
            + "\n - ".join("{} ({})".format(*x) for x in self.history),
            modification_size=str(MODIFICATION_HISTORY),
        )


class UsageExpectation:
    """
    Class representing API usage expectation at any given time.

    Expectations help formalize the way developers are expected to use some set
    of classes, methods and other instruments.

    :attr cls:
        The class of objects this expectation object applies to.
    :attr history:
        The modification history of allowed calls from older to newer
    """

    @classmethod
    def of(cls, obj):
        """
        Get the usage expectation of a given object.

        :param obj:
            The object for which usage expectation is to be set
        :returns:
            Either a previously made object or a fresh instance of
            :class:`UsageExpectation`.
        """
        try:
            return obj.__usage_expectation
        except AttributeError:
            ua = cls(type(obj))
            obj.__usage_expectation = ua
            return ua

    def __init__(self, cls):
        """
        Initialize a new, empty, usage expectations object.

        :param cls:
            The class of objects that this usage expectation applies to.  This
            is used only to inform the developer where to look for help when
            something goes wrong.
        """
        self.cls = cls
        self._allowed_calls = {}  # type: Dict[str, str]
        self.history = deque([], maxlen=MODIFICATION_HISTORY)

    def allow(
        self, current_function: Callable, function: Callable, reason: str
    ):
        """
        Allow the current object to call the given function.

        :param current_function:
            The function that called this method. This is used to record the
            history of modifications.
        :param function:
            The function that is now allowed to be called.
        :param reason:
            A string that explains why the function is allowed to be called.
        """
        self._allowed_calls[function.__name__] = reason
        self._modified(current_function, "allow")

    def disallow(self, current_function: Callable, function: Callable):
        """
        Disallow the current object to call the given function.

        :param current_function:
            The function that called this method. This is used to record the
            history of modifications.
        :param function:
            The function that is now disallowed to be called.
        """
        del self._allowed_calls[function.__name__]
        self._modified(current_function, "disallow")

    def allow_all(
        self,
        current_function: Callable,
        function_reason: Dict[Callable, str],
        clear=True,
    ):
        """
        Allow the current object to call all given functions.

        :param current_function:
            The function that called this method. This is used to record the
            history of modifications.
        :param function_reason:
            A dictionary mapping functions to strings that explain why each
            function is allowed to be called.
        :param clear:
            If True (default), replace the current set of allowed calls with
            the new ones. If False, merge the new allowed calls into the
            existing set.
        """
        str_function_reason = {
            f.__name__: reason for f, reason in function_reason.items()
        }
        if clear:
            self._allowed_calls = str_function_reason
            action = "allow_all, clear"
        else:
            self._allowed_calls.update(str_function_reason)
            action = "allow_all, don't clear"
        self._modified(current_function, action)

    def _modified(self, current_function, action):
        self.history.append(
            (
                "{}.{}".format(
                    current_function.__self__.__class__.__name__,
                    current_function.__name__,
                ),
                action,
            )
        )

    def enforce(self, current_function: Callable):
        """
        Enforce that usage expectations of the caller are met.

        This method checks if the `current_function` is allowed to be called at
        this time or raises an UnexpectedMethodCall

        :raises UnexpectedMethodCall:
            If the expectations are not met.
        """
        # XXX: Allowed calls is a dictionary that may be freely changed by the
        # outside caller. We're unable to protect against it. Therefore the
        # optimized values (for computing what is really allowed) must be
        # obtained each time we are about to check, in enforce()
        if current_function.__name__ in self._allowed_calls:
            return
        raise UnexpectedMethodCall(
            self.cls,
            current_function.__name__,
            self._allowed_calls.items(),
            self.history,
        )
