# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# This file is part of Morris.
#
# Morris is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License
#
# Morris is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Morris.  If not, see <http://www.gnu.org/licenses/>.
"""
morris.tests
============
Test definitions for Morris
"""
from __future__ import print_function, absolute_import, unicode_literals

from unittest import TestCase
from doctest import DocTestSuite

from plainbox.vendor.morris import Signal
from plainbox.vendor.morris import SignalTestCase
from plainbox.vendor.morris import boundmethod
from plainbox.vendor.morris import remove_signals_listeners
from plainbox.vendor.morris import signal
from plainbox.vendor.morris import signaldescriptor


def load_tests(loader, tests, ignore):
    from plainbox.vendor import morris
    tests.addTests(DocTestSuite(morris))
    return tests


class FakeSignalTestCase(SignalTestCase):
    """
    A subclass of :class:`morris.SignalTestCase` that defines :meth:`runTest()`
    """

    def runTest(self):
        """
        An empty test method
        """


class SignalTestCaseTest(TestCase):
    """
    Test definitions for the :class:`morris.SignalTestCase` class.
    """

    def setUp(self):
        self.signal = Signal('signal')
        self.case = FakeSignalTestCase()

    def test_watchSignal(self):
        """
        Ensure that calling watchSignal() actually connects a signal listener
        """
        self.assertEqual(len(self.signal.listeners), 0)
        self.case.watchSignal(self.signal)
        self.assertEqual(len(self.signal.listeners), 1)

    def test_assertSignalFired(self):
        """
        Ensure that assertSignalFired works correctly
        """
        self.case.watchSignal(self.signal)
        self.signal.fire((), {})
        sig = self.case.assertSignalFired(self.signal)
        self.assertEqual(sig,  (self.signal, (), {}))

    def test_assertSignalNotFired(self):
        """
        Ensure that assertSignalNotFired works correctly
        """
        self.case.watchSignal(self.signal)
        self.case.assertSignalNotFired(self.signal)

    def test_assertSignalOrdering(self):
        """
        Ensure that assertSignalOrdering works correctly
        """
        self.case.watchSignal(self.signal)
        self.signal('first')
        self.signal('second')
        self.signal('third')
        first = self.case.assertSignalFired(self.signal, 'first')
        second = self.case.assertSignalFired(self.signal, 'second')
        third = self.case.assertSignalFired(self.signal, 'third')
        self.case.assertSignalOrdering(first, second, third)


class C1(object):
    """
    Helper class with two signals defined using :meth:`Signal.define`
    """

    def on_foo(self, *args, **kwargs):
        """
        A signal accepting (ignoring) arbitrary arguments
        """

    on_foo_func = on_foo
    on_foo = Signal.define(on_foo)

    @Signal.define
    def on_bar(self):
        """
        A signal accepting no arguments
        """


class C2(object):
    """
    Helper class with two signals defined using :class:`morris.signal`
    """

    def on_foo(self, *args, **kwargs):
        """
        A signal accepting (ignoring) arbitrary arguments
        """

    on_foo_func = on_foo
    on_foo = signal(on_foo)

    @signal
    def on_bar(self):
        """
        A signal accepting no arguments
        """


class NS(object):
    """
    Helper namespace-like class
    """


def get_foo_bar():
    """
    Helper function that returns two functions, on_foo() and on_bar(), similar
    to what :class:`C1` and :class:`C2` define internally.
    """
    def on_foo(*args, **kwargs):
        """
        A signal accepting (ignoring) arbitrary arguments
        """
    def on_bar():
        """
        A signal accepting no arguments
        """
    return on_foo, on_bar


def M1():
    """
    Helper function that returns a module-like thing with two signals defined
    using :meth:`Signal.define`
    """
    on_foo, on_bar = get_foo_bar()
    ns = NS()
    ns.on_foo_func = on_foo
    ns.on_foo = Signal.define(on_foo)
    ns.on_bar = Signal.define(on_bar)
    return ns


def M2():
    """
    Helper function that returns a module-like thing with two signals defined
    using :class:`signal`
    """
    on_foo, on_bar = get_foo_bar()
    ns = NS()
    ns.on_foo_func = on_foo
    ns.on_foo = signal(on_foo)
    ns.on_bar = signal(on_bar)
    return ns


class R(object):
    """
    Helper class that collaborates with either :class:`C1` or :class:`C2`
    """

    def __init__(self, c):
        c.on_foo.connect(self._foo)
        c.on_bar.connect(self._bar)
        c.on_bar.connect(self._baz)

    def _foo(self):
        pass

    def _bar(self):
        pass

    def _baz(self):
        pass


class SignalTestsBase(object):
    """
    Set of base test definitions for :class:`morris.Signal` class.
    """

    def setUp(self):
        self.c = self.get_c()

    def test_sanity(self):
        """
        Ensure that :meth:`get_c()` is not faulty
        """
        self.assertIsInstance(self.c.on_foo, Signal)
        self.assertNotIsInstance(self.c.on_foo_func, Signal)
        self.assertNotIsInstance(self.c.on_foo_func, signaldescriptor)
        self.assertEqual(len(self.c.on_foo.listeners), 1)
        self.assertIsInstance(self.c.on_bar, Signal)
        self.assertEqual(len(self.c.on_bar.listeners), 1)

    def get_c(self):
        raise NotImplementedError

    def test_connect(self):
        """
        Ensure that connecting signals works
        """
        def handler():
            pass
        self.c.on_foo.connect(handler)
        self.assertIn(
            handler, (info.listener for info in self.c.on_foo.listeners))

    def test_disconnect(self):
        """
        Ensure that disconnecting signals works
        """
        def handler():
            pass
        self.c.on_foo.connect(handler)
        self.c.on_foo.disconnect(handler)
        self.assertNotIn(
            handler, (info.listener for info in self.c.on_foo.listeners))

    def test_calling_signal_fires_them(self):
        """
        Ensure that calling signals fires them
        """
        self.watchSignal(self.c.on_foo)
        self.c.on_foo()
        self.assertSignalFired(self.c.on_foo)

    def test_calling_signals_passes_positional_arguments(self):
        """
        Ensure that calling the signal object with positional arguments works
        """
        self.watchSignal(self.c.on_foo)
        self.c.on_foo(1, 2, 3)
        self.assertSignalFired(self.c.on_foo, 1, 2, 3)

    def test_calling_signals_passes_keyword_arguments(self):
        """
        Ensure that calling the signal object with keyword arguments works
        """
        self.watchSignal(self.c.on_foo)
        self.c.on_foo(one=1, two=2, three=3)
        self.assertSignalFired(self.c.on_foo, one=1, two=2, three=3)

    def test_remove_signals_listeners(self):
        """
        Ensure that calling :func:`remove_signal_listeners()` works
        """
        a = R(self.c)
        b = R(self.c)
        self.assertEqual(len(a.__listeners__), 3)
        self.assertEqual(len(b.__listeners__), 3)
        remove_signals_listeners(a)
        self.assertEqual(len(a.__listeners__), 0)
        self.assertEqual(len(b.__listeners__), 3)


class SignalsOnMethods(object):
    """
    Mix-in for C1 and C2-based tests
    """

    def test_first_responder(self):
        """
        Ensure that using the decorator syntax connects the decorated object
        as the first responder
        """
        self.assertEqual(len(self.c.on_foo.listeners), 1)
        # NOTE: this is a bit hairy. The ``signal`` decorator is always called
        # on the bare function object (so on the ``on_foo`` function, before
        # it becomes a method.
        #
        # To test that we need to extract the bare function (using the __func__
        # property) from the (real) boundmethod that we see as
        # self.c.on_foo_func.
        #
        # Then on top of that, the first responder is treated specially
        # by ``signal.__get__()`` so that it creates a fake boundmethod
        # (implemented in morris, not by python built-in) that stores the
        # signal and the instance manually.
        first_info = self.c.on_foo.listeners[0]
        first_listener = first_info.listener
        self.assertIsInstance(first_listener, boundmethod)
        self.assertEqual(first_listener.instance, self.c)
        self.assertEqual(first_listener.func, self.c.on_foo_func.__func__)
        self.assertEqual(first_info.pass_signal, False)


class SignalsOnFunctions(object):
    """
    Mix-in for M1 and M2-based tests
    """

    def test_first_responder(self):
        """
        Ensure that using the decorator syntax connects the decorated object as
        the first responder
        """
        self.assertEqual(len(self.c.on_foo.listeners), 1)
        first_info = self.c.on_foo.listeners[0]
        first_listener = first_info.listener
        self.assertEqual(first_listener, self.c.on_foo_func)
        self.assertEqual(first_info.pass_signal, False)


class SignalTestsC1(SignalTestsBase, SignalsOnMethods, SignalTestCase):
    """
    Test definitions for :class:`morris.Signal` class that use :class:`C1`
    """

    def get_c(self):
        return C1()


class SignalTestsC2(SignalTestsBase, SignalsOnMethods, SignalTestCase):
    """
    Test definitions for :class:`morris.Signal` class that use :class:`C2`
    """

    def get_c(self):
        return C2()


class SignalTestsM1(SignalTestsBase, SignalsOnFunctions, SignalTestCase):
    """
    Test definitions for :class:`morris.Signal` class that use :func:`M1`
    """

    def get_c(self):
        return M1()


class SignalTestsM2(SignalTestsBase, SignalsOnFunctions, SignalTestCase):
    """
    Test definitions for :class:`morris.Signal` class that use :func:`M2`
    """

    def get_c(self):
        return M2()
