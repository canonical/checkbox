# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Support code for enforcing usage expectations on public API."""

import inspect
import logging
import warnings

__all__ = ('UsageExpectation',)

_logger = logging.getLogger("plainbox.developer")


class OffByOneBackWarning(UserWarning):

    """Warning on incorrect use of UsageExpectations(self).enforce(back=2)."""


class DeveloperError(Exception):

    """
    Exception raised when program flow is incorrect.

    This exception is meant to gently educate the developer about a mistake in
    his or her choices in the flow of calls. Some classes may use it to explain
    that a precondition was not met. Applications are not intended to catch
    this exception.
    """

    pass  # Eh, PEP-257 checkers...


# NOTE: This is not meant for internationalization. There is some string
# manipulation associated with this that would be a bit more cumbersome to do
# "correctly" for the small benefit.
_msg_template = """
Uh, oh...

You are not expected to call {cls_name}.{fn_name}() at this time.

If you see this message then there is a bug somewhere in your code. We are
sorry for this. Perhaps the documentation is flawed, incomplete or confusing.
Please reach out to us if  this happens more often than you'd like.

The set of allowed calls, at this time, is:

{allowed_calls}

Refer to the documentation of {cls_name} for details.
    TIP: python -m pydoc {cls_module}.{cls_name}
"""


class UnexpectedMethodCall(DeveloperError):

    """
    Developer error reported when an unexpected method call is made.

    This type of error is reported when some set of methods is expected to be
    called in a given way but that expectation was not followed.
    """

    def __init__(self, cls, fn_name, allowed_pairs):
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
        """
        self.cls = cls
        self.fn_name = fn_name
        self.allowed_pairs = allowed_pairs

    def __str__(self):
        """Get a developer-friendly message that describes the problem."""
        return _msg_template.format(
            cls_module=self.cls.__module__,
            cls_name=self.cls.__name__,
            fn_name=self.fn_name,
            allowed_calls='\n'.join(
                ' - call {}.{}() to {}.'.format(
                    self.cls.__name__, allowed_fn_name, why)
                for allowed_fn_name, why in self.allowed_pairs))


class UsageExpectation:

    """
    Class representing API usage expectation at any given time.

    Expectations help formalize the way developers are expected to use some set
    of classes, methods and other instruments. Technically, they also encode
    the expectations and can raise :class:`DeveloperError`.

    :attr allowed_calls:
        A dictionary mapping from bound methods / functions to the use case
        explaining how that method can be used at the given moment. This works
        best if the usage is mostly linear (call foo.a(), then foo.b(), then
        foo.c()).

        This attribute can be set directly for simplicity.

    :attr cls:
        The class of objects this expectation object applies to.
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
        self.allowed_calls = {}

    def enforce(self, back=1):
        """
        Enforce that usage expectations of the caller are met.

        :param back:
            How many function call frames to climb to look for caller.  By
            default we always go one frame back (the immediate caller) but if
            this is used in some decorator or other similar construct then you
            may need to pass a bigger value.

            Depending on this value, the error message displayed to the
            developer will be either spot-on or downright wrong and confusing.
            Make sure the value you use it correct!

        :raises DeveloperError:
            If the expectations are not met.
        """
        # XXX: Allowed calls is a dictionary that may be freely changed by the
        # outside caller. We're unable to protect against it. Therefore the
        # optimized values (for computing what is really allowed) must be
        # obtained each time we are about to check, in enforce()
        allowed_code = frozenset(
            func.__wrapped__.__code__
            if hasattr(func, '__wrapped__') else func.__code__
            for func in self.allowed_calls
        )
        caller_frame = inspect.stack(0)[back][0]
        if back > 1:
            alt_caller_frame = inspect.stack(0)[back - 1][0]
        else:
            alt_caller_frame = None
        _logger.debug("Caller code: %r", caller_frame.f_code)
        _logger.debug("Alternate code: %r",
                      alt_caller_frame.f_code if alt_caller_frame else None)
        _logger.debug("Allowed code: %r", allowed_code)
        try:
            if caller_frame.f_code in allowed_code:
                return
            # This can be removed later, it allows the caller to make an
            # off-by-one mistake and go away with it.
            if (alt_caller_frame is not None and
                    alt_caller_frame.f_code in allowed_code):
                warnings.warn(
                    "Please back={}. Properly constructed decorators are"
                    " automatically handled and do not require the use of the"
                    " back argument.".format(back - 1), OffByOneBackWarning,
                    back)
                return
            fn_name = caller_frame.f_code.co_name
            allowed_undecorated_calls = {
                func.__wrapped__ if hasattr(func, '__wrapped__') else func: msg
                for func, msg in self.allowed_calls.items()
            }
            allowed_pairs = tuple(
                (fn.__code__.co_name, why)
                for fn, why in sorted(
                    allowed_undecorated_calls.items(),
                    key=lambda fn_why: fn_why[0].__code__.co_name)
            )
            raise UnexpectedMethodCall(self.cls, fn_name, allowed_pairs)
        finally:
            del caller_frame
            if alt_caller_frame is not None:
                del alt_caller_frame
