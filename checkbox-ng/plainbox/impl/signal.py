# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.signal` -- signal system
============================================
"""
from collections import defaultdict
import inspect
import logging

from plainbox.i18n import gettext as _

logger = logging.getLogger("plainbox.signal")

__all__ = ['Signal']


class Signal:
    """
    Basic signal that supports arbitrary listeners.

    While this class can be used directly it is best used with the helper
    decorator Signal.define on a member function. The function body is ignored,
    apart from the documentation.

    The function name then becomes a unique (per encapsulating class instance)
    object (an instance of this Signal class) that is created on demand.

    In practice you just have a documentation and use
    `object.signal_name.connect()` and `object.signal_name(*args, **kwargs)` to
    fire it.
    """

    def __init__(self, signal_name):
        """
        Construct a signal with the given name
        """
        self._listeners = []
        self._signal_name = signal_name

    def __repr__(self):
        return "<Signal name:{!r}>".format(self._signal_name)

    def connect(self, listener):
        """
        Connect a new listener to this signal

        That listener will be called whenever fire() is invoked on the signal
        """
        self._listeners.append(listener)
        # TRANSLATORS: this is a indicative statement
        logger.debug(_("connect %r to %r"), str(listener), self._signal_name)
        # Track listeners in the instances only
        if inspect.ismethod(listener):
            listener_object = listener.__self__
            # Ensure that the instance has __listeners__ property
            if not hasattr(listener_object, "__listeners__"):
                listener_object.__listeners__ = defaultdict(list)
            # Append the signals a listener is connected to
            listener_object.__listeners__[listener].append(self)

    def disconnect(self, listener):
        """
        Disconnect an existing listener from this signal
        """
        self._listeners.remove(listener)
        logger.debug(
            # TRANSLATORS: this is a indicative statement
            _("disconnect %r from %r"), str(listener), self._signal_name)
        if inspect.ismethod(listener):
            listener_object = listener.__self__
            if hasattr(listener_object, "__listeners__"):
                listener_object.__listeners__[listener].remove(self)
                # Remove the listener from the list if any signals connected
                if (len(listener_object.__listeners__[listener])) == 0:
                    del listener_object.__listeners__[listener]

    def fire(self, args, kwargs):
        """
        Fire this signal with the specified arguments and keyword arguments.

        Typically this is used by using __call__() on this object which is more
        natural as it does all the argument packing/unpacking transparently.
        """
        for listener in self._listeners:
            listener(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """
        Call fire() with all arguments forwarded transparently
        """
        self.fire(args, kwargs)

    @classmethod
    def define(cls, first_responder, signal_name=None):
        """
        Helper decorator to define a signal descriptor in a class

        The decorated function is never called but is used to get
        documentation.
        """
        return _SignalDescriptor(first_responder, signal_name)


class _SignalDescriptor:
    """
    Descriptor for convenient signal access.

    Typically this class is used indirectly, when accessed from Signal.define
    method decorator. It is used to do all the magic required when accessing
    signal name on a class or instance.
    """

    def __init__(self, first_responder, signal_name=None):
        if signal_name is None:
            if hasattr(first_responder, '__qualname__'):
                signal_name = first_responder.__qualname__
            else:
                signal_name = first_responder.__name__
        self.signal_name = signal_name
        self.first_responder = first_responder
        self.__doc__ = first_responder.__doc__

    def __repr__(self):
        return "<SignalDecorator for signal:{!r}>".format(self.signal_name)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        # Ensure that the instance has __signals__ property
        if not hasattr(instance, "__signals__"):
            instance.__signals__ = {}
        # Ensure that the instance signal is defined
        if self.signal_name not in instance.__signals__:
            # Or create it if needed
            signal = Signal(self.signal_name)
            # Connect the first responder function
            signal.connect(lambda *args, **kwargs: self.first_responder(
                instance, *args, **kwargs))
            # Ensure we don't recreate signals
            instance.__signals__[self.signal_name] = signal
        return instance.__signals__[self.signal_name]

    def __set__(self, instance, value):
        raise AttributeError("You cannot overwrite signals")

    def __delete__(self, instance):
        raise AttributeError("You cannot delete signals")


def remove_signals_listeners(instance):
    """
    utility function that disconnects all listeners from all signals on an
    object
    """
    if hasattr(instance, "__listeners__"):
        for listener in list(instance.__listeners__):
            for signal in instance.__listeners__[listener]:
                signal.disconnect(listener)


class SignalInterceptorMixIn:
    """
    A mix-in class for :class:`unittest.TestCase` that simplifies testing
    uses of the plainbox signal system
    """

    def _extend_state(self):
        if not hasattr(self, '_events_seen'):
            self._events_seen = []

    def watchSignal(self, signal):
        """
        Setup provisions to watch a specified signal

        :param signal:
            The signal (from :mod:`plainbox.impl.signal`) to watch.
        """
        self._extend_state()

        def signal_handler(*args, **kwargs):
            self._events_seen.append((signal, args, kwargs))
        signal.connect(signal_handler)
        if hasattr(self, 'addCleanup'):
            self.addCleanup(signal.disconnect, signal_handler)

    def assertSignalFired(self, signal, *args, **kwargs):
        """
        Assert that a signal was fired with appropriate arguments.

        :param signal:
            The signal (from :mod:`plainbox.impl.signal`) that should have been
            fired. Typically this is ``SomeClass.on_some_signal`` reference
        :param args:
            List of positional arguments passed to the signal handler
        :param kwargs:
            List of keyword arguments passed to the signal handler
        :returns:
            A 3-tuple (signal, args, kwargs) that describes that event
        """
        event = (signal, args, kwargs)
        self.assertIn(event, self._events_seen)
        return event

    def assertSignalNotFired(self, signal, *args, **kwargs):
        """
        Assert that a signal was fired with appropriate arguments.

        :param signal:
            The signal (from :mod:`plainbox.impl.signal`) that should have been
            fired. Typically this is ``SomeClass.on_some_signal`` reference
        :param args:
            List of positional arguments passed to the signal handler
        :param kwargs:
            List of keyword arguments passed to the signal handler
        """
        event = (signal, args, kwargs)
        self.assertNotIn(event, self._events_seen)

    def assertSignalOrdering(self, *expected_events):
        """
        Assert that a signals were fired in a specific sequence.

        :param expected_events:
            A (varadic) list of events describing the signals that were fired
            Each element is a 3-tuple (signal, args, kwargs) that describes
            the event.

        .. note::
            If you are using :meth:`assertSignalFired()` then the return value
            of that method is a single event that can be passed to this method
        """
        expected_order = [self._events_seen.index(event)
                          for event in expected_events]
        actual_order = sorted(expected_order)
        self.assertEqual(
            expected_order, actual_order,
            "\nExpected order of fired signals:\n{}\n"
            "Actual order observed:\n{}".format(
                "\n".join(
                    "\t{}: {}".format(i, event)
                    for i, event in enumerate(expected_events, 1)),
                "\n".join(
                    "\t{}: {}".format(i, event)
                    for i, event in enumerate(
                        (self._events_seen[idx] for idx in actual_order), 1))))
