# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This file is part of Morris.
#
# Morris is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# Morris is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Morris.  If not, see <http://www.gnu.org/licenses/>.
"""
:mod:`plainbox.vendor.morris` --  announcement (signal/event) system for Python
===============================================================

The plainbox.vendor.morris module defines two main classes :class:`signal` and
:class:`SignalTestCase`.

Defining Signals
----------------

.. note::
    Since version 1.1 ``Signal.define`` and ``signal`` are identical

You can import the ``signal`` class and use idiomatic code like::

    >>> from plainbox.vendor.morris import signal

    >>> # NOTE: classic python 2.x classes are not supported
    >>> class Klass(object):
    ...     @signal
    ...     def on_foo(self):
    ...         pass

    >>> @signal
    ... def on_bar():
    ...     pass

Connecting signal listeners
---------------------------

Connecting signals is equally easy, just call :meth:`signal.connect()`

    >>> def handler():
    ...     print("handling signal")

    >>> obj = Klass()
    >>> obj.on_foo.connect(handler)
    >>> on_bar.connect(handler)

Firing signals
--------------

To fire a signal simply *call* the signal object::

    >>> obj.on_foo()
    handling signal
    >>> on_bar()
    handling signal

Typically you will want to pass some additional arguments. Both positional
and keyword arguments are supported::

    >>> @signal
    ... def on_bar_with_args(arg1, arg2):
    ...     print("fired!")

    >>> on_bar_with_args('foo', arg2='bar')
    fired!

If you are working in a tight loop it is slightly faster to construct the list
of positional arguments and the dictionary of keyword arguments and call the
:meth:`Signal.fire()` method directly::

    >>> args = ('foo',)
    >>> kwargs = {'arg2': 'bar'}
    >>> for i in range(3):
    ...     on_bar_with_args.fire(args, kwargs)
    fired!
    fired!
    fired!

Passing additional meta-data to the signal listener
---------------------------------------------------

In some cases you may wish to use a generic signal handler that would benefit
from knowing which signal has triggered it. To do that first make sure that
your handler has a ``signal`` argument and then call ``sig.connect(handler,
pass_signal=True)``:

    >>> def generic_handler(*args, **kwargs):
    ...     signal = kwargs.pop('signal')
    ...     print("Handling signal {}: {} {}".format(signal, args, kwargs))

Let's define two signals now:

    >>> @signal
    ... def login(user, password):
    ...     pass
    >>> @signal
    ... def logout(user):
    ...     pass

And connect both to the same handler:

    >>> login.connect(generic_handler, pass_signal=True)
    >>> logout.connect(generic_handler, pass_signal=True)

Now we can fire either one and see our handler work:

    >>> login(str('user'), password=str('pass'))
    Handling signal <signal name:'login'>: ('user',) {'password': 'pass'}
    >>> logout(str('user'))
    Handling signal <signal name:'logout'>: ('user',) {}

.. note::
    The example uses ``str(...)`` to have identical output on Python
    2.7 and 3.x but ``str()`` it is otherwise useless.

This also works with classes:

    >>> class App(object):
    ...     def __repr__(self):
    ...         return "app"
    ...     @signal
    ...     def login(self, user, password):
    ...         pass
    ...     @signal
    ...     def logout(self, user):
    ...         pass
    >>> app = App()
    >>> app.login.connect(generic_handler, pass_signal=True)
    >>> app.logout.connect(generic_handler, pass_signal=True)

We can now fire the signals, just as before:

    >>> app.login(str('user'), password=str('pass'))
    ... # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Handling signal <signal name:'...login' (specific to app)>:
        ('user',) {'password': 'pass'}
    >>> app.logout(str('user'))  # doctest: +ELLIPSIS
    Handling signal <signal name:'...logout' (specific to app)>: ('user',) {}

Disconnecting signals
---------------------

To disconnect a signal handler call :meth:`signal.disconnect()` with the same
listener object that was used in ``connect()``:

    >>> obj.on_foo.disconnect(handler)
    >>> on_bar.disconnect(handler)

Threading considerations
------------------------

Morris doesn't do anything related to threads. Threading is diverse enough that
for now it was better to just let uses handle it. There are two things that
are worth mentioning though:

1) :meth:`signal.connect()` and :meth:`signal.disconnect()` should be safe to
   call concurrently with :meth:`signal.fire()` since fire() operates on
   a *copy* of the list of listeners

2) Event handlers are called from the thread calling :meth:`signal.fire()`,
   not from the thread that was used to connect to the signal handler. If you
   need special provisions for working with signals in a specific thread
   consider calling a thread-library-specific function that calls a callable
   in a specific thread context.

Support for writing unit tests
------------------------------

Morris ships with support for writing tests for signals. You can use
:class:`SignalTestCase`'s support methods such as
:meth:`~signalTestCase.watchSignal()`,
:meth:`~SignalTestCase.assertSignalFired()`,
:meth:`~SignalTestCase.assertSignalNotFired()` and
:meth:`~SignalTestCase.assertSignalOrdering()` to simplify your tests.

Here's a simple example using all of the above:

    >>> class App(object):
    ...     @signal
    ...     def on_login(self, user):
    ...         pass
    ...     @signal
    ...     def on_logout(self, user):
    ...         pass
    ...     def login(self, user):
    ...         self.on_login(user)
    ...     def logout(self, user):
    ...         self.on_logout(user)

    >>> class AppTests(SignalTestCase):
    ...     def setUp(self):
    ...         self.app = App()
    ...         self.watchSignal(self.app.on_login)
    ...         self.watchSignal(self.app.on_logout)
    ...     def test_login(self):
    ...         # Log the user in, then out
    ...         self.app.login("user")
    ...         self.app.logout("user")
    ...         # Ensure that both login and logout signals were sent
    ...         event1 = self.assertSignalFired(self.app.on_login, 'user')
    ...         event2 = self.assertSignalFired(self.app.on_logout, 'user')
    ...         # Ensure that signals were fired in the right order
    ...         self.assertSignalOrdering(event1, event2)
    ...         # Ensure that we didn't login as admin
    ...         self.assertSignalNotFired(self.app.on_login, 'admin')

    >>> import sys
    >>> suite = unittest.TestLoader().loadTestsFromTestCase(AppTests)
    >>> runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    >>> runner.run(suite)  # doctest: +ELLIPSIS
    test_login (plainbox.vendor.morris.AppTests) ... ok
    <BLANKLINE>
    ----------------------------------------------------------------------
    Ran 1 test in ...s
    <BLANKLINE>
    OK
    <unittest.runner.TextTestResult run=1 errors=0 failures=0>

Implementation notes
--------------------

At some point in time one may need to peek under the cover and understand where
the list of signal listeners is being stored and how signals interact with
classes. First of all, the :class:`signal` class can be used as a Python
descriptor. Descriptors are objects that have methods such as ``__get__``,
``__set__`` or ``__delete__``.

You have most certainly used descriptors before, in fact the well-known
``@property`` decorator is nothing more than a class with methods such as
listed above.

When used as a descriptor, a signal object will **create new signal objects
each time it is being accessed on an instance of some class**. The instance of
some class will be injected with a ``__signals__`` dictionary that contains
signals that have been accessed.

Consider this example::

    >>> class Foo(object):
    ...     @signal
    ...     def ping(self):
    ...         pass

Here ``Foo.ping`` is one instance of :class:`signal`. When that instance
is being accessed on a class it simply returns itself.

    >>> Foo.ping  # doctest: +ELLIPSIS
    <signal name:'...ping'>

.. note::
    While this looks similar to decorating a function it is functioning in a
    totally different way. Signals decorating plain functions (outside of a
    class definition body) are not using their descriptor nature.

Now, let's instantiate ``Foo`` and see what's inside::

    >>> foo = Foo()
    >>> foo.__dict__
    {}

Nothing is inside, but there will be once we access ``foo.ping``. Morris will
create a new :class:`signal` object associated with both the ``foo`` instance
and the ``foo.ping`` method. It will look for ``foo.__signals__`` and not
having found any will create one from an empty dictionary. Lastly morris will
add the newly created signal object to the dictionary. This way each time we
access ``foo.ping`` (on the particular ``foo`` object) we'll get exactly the
same signal object in return.

    >>> foo.ping  # doctest: +ELLIPSIS
    <signal name:'...ping' (specific to <...Foo object at ...>)>
    >>> foo.__dict__  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    {'__signals__':
     {'...ping': <signal name:'...ping'
      (specific to <...Foo object at ...>)>}}

This all happens transparently the first time that code such as
``foo.ping.connect(...)`` is executed. When you connect a signal morris simply
needs a place to store the list of listeners and that is in a signal object
itself. We can now register a simple listener.

    >>> def handler():
    ...     pass
    >>> foo.ping.connect(handler)

Handlers are stored in the :meth:`signal.listeners` attribute. They are stored
as a list of :class:`listenerinfo` tuples. Note that the first responder (the
decorated function itself) is also present, here it is wrapped in the special
(specific to morris) :class:`boundmethod` class.

    >>> foo.ping.listeners  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    [listenerinfo(listener=<...boundmethod object at ...>, pass_signal=False),
     listenerinfo(listener=<function handler at ...>, pass_signal=False)]

Now, let's compare this to using signals as a function decorator:

    >>> @signal
    ... def standalone():
    ...     pass

The ``standalone()`` function is now *replaced* by the correspondingly-named
signal object:

    >>> standalone
    <signal name:'standalone'>

The original function is connected as the first responder though:

    >>> standalone.listeners  # doctest: +ELLIPSIS
    [listenerinfo(listener=<function ...standalone at ...>, pass_signal=False)]

Since there are no extra objects, there is no ``__dict__`` and no
``__signals__`` either.


Using @signal on class with __slots__
-------------------------------------

Since (having read the previous section) you already know that signal
descriptors access the ``__signals__`` attribute on objects of classes they
belong to, to use signals on a class that uses ``__slots__`` you need to
reserve the ``__signals__`` slot up-front.

    >>> class Slotted(object):
    ...     __slots__ = ('__signals__')
    ...     @signal
    ...     def ping(self):
    ...         pass
    >>> Slotted.ping  # doctest: +ELLIPSIS
    <signal name:'...ping'>
    >>> slotted = Slotted()
    >>> slotted.ping  # doctest: +ELLIPSIS
    <signal name:'...ping' (specific to <...Slotted object at ...>)>
    >>> slotted.__signals__  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    {'...ping': <signal name:'...ping'
     (specific to <...Slotted object at ...>)>}

Creating signals explicitly
---------------------------

In all of the examples above we've been using signal as a decorator for
existing methods or functions. This is fine for the vast majority of code but
in some cases it may be beneficial to create signal objects explicitly. This
may be of use in meta-programming, for example.

The :class:`signal` class may be instantiated in the two following ways:
 - with the signal name (and no listeners)
 - with the first responder function (which becomes the first listener)

The second mode also has a special special case where the first responder.
Let's examine than now. First, the plain signal object:

    >>> signal(str("my-signal"))
    <signal name:'my-signal'>

This is a normal signal object, we can call it to fire the signal, we can use
the :meth:`signal.connect()` method to add listeners, etc. If you want to
create standalone signals, this is the best way to do it.

Now let's examine the case where we pass a signal handler instead of the name:

    >>> def my_signal2_handler():
    ...     pass
    >>> signal(my_signal2_handler)
    <signal name:'my_signal2_handler'>

Here the name of the signal is derived from the name of the handler function.
We can customize the name, if desired, by passing the signal_name argument
(preferably as a keyword argument to differentiate it from the ``pass_signal``
argument):

    >>> signal(my_signal2_handler, signal_name='my-signal-2')
    <signal name:'my-signal-2'>

Both examples that pass a handler are identical to what happens when decorating
a regular function. There is nothing special about this mode either.

The last, and somewhat special, mode is where the handler is an instance of
:class:`boundmethod` (which is implemented inside morris). In the Python 2.x
world, python had bound methods but they were removed. We still benefit from
them, a little, hence they are back.

    >>> class C(object):
    ...     def handler(self):
    ...         pass
    >>> signal(boundmethod(C(), C.handler))  # doctest: +ELLIPSIS
    <signal name:'...handler' (specific to <...C object at ...>)>

.. note::
    It is possible to remove boundmethod and rely  ``func.__self__`` but this
    was not done, yet. Contributions are welcome!

To summarize this section, some simple rules:

- each signal object has a list of listeners
- signal objects act as descriptors and create per-instance signal objects
- signal object created this way are stored in per-instance ``__signals__``
  attribute
"""
from __future__ import print_function, absolute_import, unicode_literals

import collections
import inspect
import logging
import unittest

__author__ = 'Zygmunt Krynicki'
__email__ = 'zygmunt.krynicki@canonical.com'
__version__ = '1.2'
__all__ = ['signal', 'SignalTestCase']

_logger = logging.getLogger("plainbox.vendor.morris")


listenerinfo = collections.namedtuple('listenerinfo', 'listener pass_signal')


class signal(object):
    """
    Basic signal that supports arbitrary listeners.

    While this class can be used directly it is best used with the helper
    decorator Signal.define on a function or method. See the documentation
    for the :mod:`plainbox.vendor.morris` module for details.

    :attr _name:
        Name of the signal, typically accessed via :meth:`name`.
    :attr _listeners:
        List of signal listeners. Each item is a tuple ``(listener,
        pass_signal)`` that encodes how to call the listener.
    """
    try:
        _str_bases = (str, unicode)
    except NameError:
        _str_bases = (str,)

    def __init__(self, name_or_first_responder, pass_signal=False,
                 signal_name=None):
        """
        Construct a signal with the given name

        :param name_or_first_responder:
            Either the name of the signal to construct or a callable which
            will be the first responder. In the latter case the callable is
            used to obtain the name of the signal.
        :param pass_signal:
            An optional flag that instructs morris to pass the signal object
            itself to the first responder (as the ``signal`` argument). This is
            only used in the case where ``name_or_first_responder`` is a
            callable.
        :param signal_name:
            Optional name of the signal. This is meaningful only when the first
            argument ``name_or_first_responder`` is a callable.  When that
            happens this argument is used and no guessing based on __qualname__
            or __name__ is being used.
        """
        if isinstance(name_or_first_responder, self._str_bases):
            first_responder = None
            name = name_or_first_responder
        else:
            first_responder = name_or_first_responder
            name = signal_name or _get_fn_name(first_responder)
        self._name = name
        self._first_responder = first_responder
        self._listeners = []
        if first_responder is not None:
            self._listeners.append(listenerinfo(first_responder, pass_signal))

    def __repr__(self):
        """
        A representation of the signal.

        There are two possible representations:
            - a signal object created via a signal descriptor on an object
            - a signal object acting as a descriptor or function decorator
        """
        if (len(self._listeners) > 0
                and isinstance(self.listeners[0].listener, boundmethod)):
            return "<signal name:{!r} (specific to {!r})>".format(
                str(self._name), self._listeners[0].listener.instance)
        else:
            return "<signal name:{!r}>".format(str(self._name))

    def __get__(self, instance, owner):
        """
        Descriptor __get__ method

        This method is called when a signal-decorated method is being accessed
        via an object or a class. It is never called for decorated functions.

        :param instance:
            Instance of the object the descriptor is being used on.
            This is None when the descriptor is accessed on a class.
        :param owner:
            The class that the descriptor is defined on.
        :returns:
            If ``instance`` is None we return ourselves, this is what
            descriptors typically do. If ``instance`` is not None we return a
            unique :class:`Signal` instance that is specific to that object and
            signal. This is implemented by storing the signal inside the
            object's __signals__ attribute.
        """
        if instance is None:
            return self
        # Ensure that the instance has __signals__ property
        if not hasattr(instance, "__signals__"):
            instance.__signals__ = {}
        # Ensure that the instance signal is defined
        if self._name not in instance.__signals__:
            # Or create it if needed
            signal = Signal(self._name)
            # Connect the first responder function via the trampoline so that
            # the instance's self object is also passed explicitly
            signal.connect(boundmethod(instance, self._first_responder))
            # Ensure we don't recreate signals
            instance.__signals__[self._name] = signal
        return instance.__signals__[self._name]

    def __set__(self, instance, value):
        raise AttributeError("You cannot overwrite signals")

    def __delete__(self, instance):
        raise AttributeError("You cannot delete signals")

    @property
    def name(self):
        """
        Name of the signal

        For signals constructed manually (i.e. by calling :class:`Signal()`)
        the name is arbitrary. For signals constructed using either
        :meth:`Signal.define()` or :class:`signal` the name is obtained
        from the decorated function.

        On python 3.3+ the qualified name is used (see :pep:`3155`), on earlier
        versions the plain name is used (without the class name). The name is
        identical regardless of how the signal is being accessed:

            >>> class C(object):
            ...     @signal
            ...     def on_meth(self):
            ...         pass

        As a descriptor on a class:

            >>> C.on_meth.name  # doctest: +ELLIPSIS
            '...on_meth'

        As a descriptor on an object:

            >>> C().on_meth.name  # doctest: +ELLIPSIS
            '...on_meth'

        As a decorated function:

            >>> @signal
            ... def on_func():
            ...     pass
            >>> on_func.name
            'on_func'
        """
        return self._name

    # For backwards compatibility with Plainbox-based code
    signal_name = name

    @property
    def listeners(self):
        """
        List of :class:`listenerinfo` objects associated with this signal

        The list of listeners is considered part of an implementation detail
        but is exposed for convenience. This is always the real list. Keep
        this in mind while connecting and disconnecting listeners. During
        the time :meth:`fire()` is called the list of listeners can be changed
        but won't take effect until after ``fire()`` returns.
        """
        return self._listeners

    @property
    def first_responder(self):
        """
        The first responder function.

        This is the function that the ``signal`` may have been instantiated
        with. It is only relevant if the signal itself is used as a
        *descriptor* in a class (where it decorates a method).

        For example, contrast the access of the signal on the class and on a
        class instance:

            >>> class C(object):
            ...     @signal
            ...     def on_foo(self):
            ...         pass

        Class access gives uses the descriptor protocol to expose the
        actual signal object.

            >>> C.on_foo  # doctest: +ELLIPSIS
            <signal name:'...on_foo'>

        Here we can use the ``first_responder`` property to see the actual
        function.

            >>> C.on_foo.first_responder  # doctest: +ELLIPSIS
            <function ...on_foo at ...>

        Object access is different as now the signal instance is specific to
        the object:

            >>> C().on_foo  # doctest: +ELLIPSIS
            <signal name:'...on_foo' (specific to <plainbox.vendor.morris.C object at ...)>

        And now the first responder is gone (it is now buried inside the
        :meth:`listeners` list):

            >>> C().on_foo.first_responder
        """
        return self._first_responder

    def connect(self, listener, pass_signal=False):
        """
        Connect a new listener to this signal

        :param listener:
            The listener (callable) to add
        :param pass_signal:
            An optional argument that controls if the signal object is
            explicitly passed to this listener when it is being fired.
            If enabled, a ``signal=`` keyword argument is passed to the
            listener function.
        :returns:
            None

        The listener will be called whenever :meth:`fire()` or
        :meth:`__call__()` are called.  The listener is appended to the list of
        listeners. Duplicates are not checked and if a listener is added twice
        it gets called twice.
        """
        info = listenerinfo(listener, pass_signal)
        self._listeners.append(info)
        _logger.debug("connect %r to %r", str(listener), self._name)
        # Track listeners in the instances only
        if inspect.ismethod(listener):
            listener_object = listener.__self__
            # Ensure that the instance has __listeners__ property
            if not hasattr(listener_object, "__listeners__"):
                listener_object.__listeners__ = collections.defaultdict(list)
            # Append the signals a listener is connected to
            listener_object.__listeners__[listener].append(self)

    def disconnect(self, listener, pass_signal=False):
        """
        Disconnect an existing listener from this signal

        :param listener:
            The listener (callable) to remove
        :param pass_signal:
            An optional argument that controls if the signal object is
            explicitly passed to this listener when it is being fired.
            If enabled, a ``signal=`` keyword argument is passed to the
            listener function.

            Here, this argument simply aids in disconnecting the right
            listener. Make sure to pass the same value as was passed to
            :meth:`connect()`
        :raises ValueError:
            If the listener (with the same value of pass_signal) is not present
        :returns:
            None
        """
        info = listenerinfo(listener, pass_signal)
        self._listeners.remove(info)
        _logger.debug(
            "disconnect %r from %r", str(listener), self._name)
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

        Typically this is used by using :meth:`__call__()` on this object which
        is more natural as it does all the argument packing/unpacking
        transparently.
        """
        for info in self._listeners[:]:
            if info.pass_signal:
                info.listener(*args, signal=self, **kwargs)
            else:
                info.listener(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """
        Call fire() with all arguments forwarded transparently

        This is provided for convenience so that a signal can be fired just
        by a simple method or function call and so that signals can be passed
        to other APIs that don't understand the :meth:`fire()` method.
        """
        self.fire(args, kwargs)

# In the past this used to be a helper method for defining signals.
# Now the same functionality is available through the signal class.
signal.define = signal


# In the past this used to be the actual signal class that knows about
# listeners. Now that is all merged into the one ``signal`` class.
Signal = signal


# In the past this used to be the signal descriptor class that knows about
# the first responder and knows how to create :class:`Signal` objects. Now
# that is all merged into the one ``signal`` class.
signaldescriptor = signal


def _get_fn_name(fn):
    if hasattr(fn, '__qualname__'):
        return fn.__qualname__
    else:
        return fn.__name__


class boundmethod(object):
    """
    A helper class that allows us to emulate a bound method

    This class emulates a bond method by storing an object ``instance``,
    function ``func`` and calling ``instance``.``func``() whenever the
    boundmethod object itself is called.
    """

    def __init__(self, instance, func):
        self.instance = instance
        self.func = func
        if hasattr(func, '__qualname__'):
            self.__qualname__ = self.func.__qualname__
        self.__name__ = self.func.__name__

    def __call__(self, *args, **kwargs):
        return self.func(self.instance, *args, **kwargs)


class SignalInterceptorMixIn:
    """
    A mix-in class for TestCase-like classes that adds extra methods for
    working with and testing signals. This class may be of use if the base
    TestCase class is not the standard ``unittest.TestCase`` class but the user
    still wants to take advantage of the extra methods provided here.
    """

    def _extend_state(self):
        if not hasattr(self, '_events_seen'):
            self._events_seen = []

    def watchSignal(self, signal):
        """
        Setup provisions to watch a specified signal

        :param signal:
            The :class:`Signal` to watch for.

        After calling this method you can use :meth:`assertSignalFired()`
        and :meth:`assertSignalNotFired()` with the same signal.
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
            The :class:`Signal` that should have been fired.
            Typically this is ``SomeClass.on_some_signal`` reference
        :param args:
            List of positional arguments passed to the signal handler
        :param kwargs:
            List of keyword arguments passed to the signal handler
        :returns:
            A 3-tuple (signal, args, kwargs) that describes that event
        """
        event = (signal, args, kwargs)
        self.assertIn(
            event, self._events_seen,
            "\nSignal unexpectedly not fired: {}\n".format(event))
        return event

    def assertSignalNotFired(self, signal, *args, **kwargs):
        """
        Assert that a signal was fired with appropriate arguments.

        :param signal:
            The :class:`Signal` that should not have been fired.
            Typically this is ``SomeClass.on_some_signal`` reference
        :param args:
            List of positional arguments passed to the signal handler
        :param kwargs:
            List of keyword arguments passed to the signal handler
        """
        event = (signal, args, kwargs)
        self.assertNotIn(
            event, self._events_seen,
            "\nSignal unexpectedly fired: {}\n".format(event))

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


class SignalTestCase(unittest.TestCase, SignalInterceptorMixIn):
    """
    A :class:`unittest.TestCase` subclass that simplifies testing uses of
    the Morris signals. It provides three assertion methods and one utility
    helper method for observing signal events.
    """


def remove_signals_listeners(instance):
    """
    utility function that disconnects all listeners from all signals on an
    object
    """
    if hasattr(instance, "__listeners__"):
        for listener in list(instance.__listeners__):
            for signal in instance.__listeners__[listener]:
                signal.disconnect(listener)
