# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
import doctest
import operator
import sys
import unittest

from plainbox.impl.proxy import _logger
from plainbox.impl.proxy import proxy
from plainbox.impl.proxy import unproxied
from plainbox.vendor import mock


# XXX: Set to True for revelation
reality_is_broken = False


def load_tests(loader, tests, ignore):
    tests.addTests(
        doctest.DocTestSuite('plainbox.impl.proxy',
                             optionflags=doctest.REPORT_NDIFF))
    return tests


def setUpModule():
    if reality_is_broken:
        # If you start to doubt reality
        from plainbox.impl.logging import adjust_logging
        from plainbox.impl.logging import setup_logging
        setup_logging()
        adjust_logging('DEBUG', ['plainbox.proxy'], True)


class proxy_as_function(unittest.TestCase):

    def setUp(self):
        if reality_is_broken:
            print()
            _logger.debug("STARTING")
            _logger.debug("[%s]", self._testMethodName)
        self.obj = mock.MagicMock(name='obj')
        self.proxy = proxy(self.obj)

    def tearDown(self):
        if reality_is_broken:
            _logger.debug("DONE")

    # NOTE: order of test methods matches implementation

    def test_repr(self):
        self.assertEqual(repr(self.proxy), repr(self.obj))
        self.assertEqual(self.proxy.__repr__(), repr(self.obj))

    def test_str(self):
        self.assertEqual(str(self.proxy), str(self.obj))
        self.assertEqual(self.proxy.__str__(), str(self.obj))

    def test_bytes(self):
        # NOTE: bytes() is unlike str() or repr() in that it is not a function
        # that converts an arbitrary object into a bytes object.  We cannot
        # just call it on a random object. What we must do is implement
        # __bytes__() on a new class and use instances of that class.
        class C:
            def __bytes__(self):
                return b'good'
        self.obj = C()
        self.proxy = proxy(self.obj)
        self.assertEqual(bytes(self.proxy), bytes(self.obj))
        self.assertEqual(self.proxy.__bytes__(), bytes(self.obj))

    def test_format(self):
        self.assertEqual(format(self.proxy), format(self.obj))
        self.assertEqual(self.proxy.__format__(""), format(self.obj))

    def test_lt(self):
        # NOTE: MagicMock is not ordered so let's just use an integer
        self.obj = 0
        self.proxy = proxy(self.obj)
        self.assertLess(self.proxy, 1)
        self.assertLess(self.obj, 1)

    def test_le(self):
        # NOTE: MagicMock is not ordered so let's just use an integer
        self.obj = 0
        self.proxy = proxy(self.obj)
        self.assertLessEqual(self.proxy, 0)
        self.assertLessEqual(self.proxy, 1)
        self.assertLessEqual(self.obj, 0)
        self.assertLessEqual(self.obj, 1)

    def test_eq(self):
        self.assertEqual(self.proxy, self.obj)
        self.obj.__eq__.assert_called_once_with(self.obj)
        self.assertEqual(self.obj, self.obj)

    def test_ne(self):
        other = object()
        self.assertNotEqual(self.proxy, other)
        self.obj.__ne__.assert_called_once_with(other)
        self.assertNotEqual(self.obj, object())

    def test_gt(self):
        # NOTE: MagicMock is not ordered so let's just use an integer
        self.obj = 0
        self.proxy = proxy(self.obj)
        self.assertGreater(self.proxy, -1)
        self.assertGreater(self.obj, -1)

    def test_ge(self):
        # NOTE: MagicMock is not ordered so let's just use an integer
        self.obj = 0
        self.proxy = proxy(self.obj)
        self.assertGreaterEqual(self.proxy, 0)
        self.assertGreaterEqual(self.proxy, -1)
        self.assertGreaterEqual(self.obj, 0)
        self.assertGreaterEqual(self.obj, -1)

    def test_hash(self):
        self.assertEqual(hash(self.proxy), hash(self.obj))
        self.assertEqual(self.proxy.__hash__(), hash(self.obj))

    def test_bool(self):
        self.assertEqual(bool(self.proxy), bool(self.obj))
        self.assertEqual(self.proxy.__bool__(), bool(self.obj))

    def test_attr_get(self):
        self.assertIs(self.proxy.attr, self.obj.attr)

    def test_attr_set(self):
        value = mock.Mock(name='value')
        self.proxy.attr = value
        self.assertIs(self.obj.attr, value)

    def test_attr_del(self):
        del self.proxy.attr
        with self.assertRaises(AttributeError):
            self.obj.attr

    def test_dir(self):
        self.assertEqual(dir(self.proxy), dir(self.obj))
        self.assertEqual(self.proxy.__dir__(), dir(self.obj))

    def test_descriptor_methods(self):
        # NOTE: this tests __get__, __set__ and __delete__ in one test, for
        # brevity
        property_proxy = proxy(property)

        class C:
            _ok = "default"

            @property_proxy
            def ok(self):
                return self._ok

            @ok.setter
            def ok(self, value):
                self._ok = value

            @ok.deleter
            def ok(self):
                del self._ok
        obj = C()
        self.assertEqual(obj._ok, "default")
        # __set__ assigns the new value
        obj.ok = True
        self.assertTrue(obj._ok)
        # __get__ returns the current value
        self.assertTrue(obj.ok)
        # __delete__ removes the current value
        del obj.ok
        self.assertEqual(obj._ok, "default")

    def test_call(self):
        self.assertEqual(self.proxy(), self.obj())
        self.assertEqual(self.proxy.__call__(), self.obj())

    def test_len(self):
        self.assertEqual(len(self.proxy), len(self.obj))
        self.assertEqual(self.proxy.__len__(), len(self.obj))

    @unittest.skipIf(lambda: sys.version_info[0:2] < 3, 4)
    def test_length_hint(self):
        # NOTE: apparently MagicMock doesn't support this method
        class C:
            def __length_hint__(self):
                return 42
        self.obj = C()
        self.proxy = proxy(self.obj)
        self.assertEqual(
            operator.length_hint(self.proxy), operator.length_hint(self.obj))
        self.assertEqual(
            self.proxy.__length_hint__(), operator.length_hint(self.obj))

    def test_getitem(self):
        self.assertEqual(self.proxy['item'], self.obj['item'])
        self.assertEqual(self.proxy.__getitem__('item'), self.obj['item'])

    def test_setitem_v1(self):
        # NOTE: MagicMock doesn't store item assignment
        self.obj = ["old"]
        self.proxy = proxy(self.obj)
        self.proxy[0] = "new"
        self.assertEqual(self.obj[0], "new")

    def test_setitem_v2(self):
        # NOTE: MagicMock doesn't store item assignment
        self.obj = ["old"]
        self.proxy = proxy(self.obj)
        self.proxy.__setitem__(0, "value")
        self.assertEqual(self.obj[0], "value")

    def test_delitem(self):
        obj = {'k': 'v'}
        del proxy(obj)['k']
        self.assertEqual(obj, {})
        obj = {'k': 'v'}
        proxy(obj).__delitem__('k')
        self.assertEqual(obj, {})

    def test_iter(self):
        # NOTE: MagicMock.__iter__ needs to return a deterministic iterator as
        # by default a new iterator is returned each time.
        self.obj.__iter__.return_value = iter([])
        self.assertEqual(iter(self.proxy), iter(self.obj))
        self.assertEqual(self.proxy.__iter__(), iter(self.obj))

    def test_reversed(self):
        # NOTE: apparently MagicMock.doesn't support __reversed__ so we fall
        # back to the approach with a custom class. The same comment, as above,
        # for __iter__() applies though.
        with self.assertRaises(AttributeError):
            self.obj.__reversed__.return_value = reversed([])

        class C:
            reversed_retval = iter([])

            def __reversed__(self):
                return self.reversed_retval
        self.obj = C()
        self.proxy = proxy(self.obj)
        self.assertEqual(reversed(self.proxy), reversed(self.obj))
        self.assertEqual(self.proxy.__reversed__(), reversed(self.obj))

    def test_contains(self):
        item = object()
        self.assertEqual(item in self.proxy, item in self.obj)
        self.assertEqual(self.proxy.__contains__(item), item in self.obj)
        self.assertEqual(self.proxy.__contains__(item), False)
        self.obj.__contains__.return_value = True
        self.assertEqual(item in self.proxy, item in self.obj)
        self.assertEqual(self.proxy.__contains__(item), item in self.obj)
        self.assertEqual(self.proxy.__contains__(item), True)

    # TODO, tests and implementation for all the numeric methods

    def test_context_manager_methods_v1(self):
        with self.proxy:
            pass
        self.obj.__enter__.assert_called_once_with()
        self.obj.__exit__.assert_called_once_with(None, None, None)

    def test_context_manager_methods_v2(self):
        exc = Exception("boom")
        with self.assertRaisesRegex(Exception, "boom"):
            with self.proxy:
                raise exc
        self.obj.__enter__.assert_called_once_with()
        # XXX: it's called with (Exception, exc, traceback) but I don't know
        # how to reach the traceback here
        self.obj.__exit__.assert_called_once

    def test_hasattr_parity(self):
        class C():
            pass
        special_methods = '''
            __del__
            __repr__
            __str__
            __bytes__
            __format__
            __lt__
            __le__
            __eq__
            __ne__
            __gt__
            __ge__
            __hash__
            __bool__
            __getattr__
            __getattribute__
            __setattr__
            __delattr__
            __dir__
            __get__
            __set__
            __delete__
            __call__
            __len__
            __length_hint__
            __getitem__
            __setitem__
            __delitem__
            __iter__
            __reversed__
            __contains__
            __enter__
            __exit__
        '''.split()
        for obj in [C(), 42, property(lambda x: x), int, None]:
            self.obj = obj
            self.proxy = proxy(self.obj)
            for attr in special_methods:
                self.assertEqual(
                    hasattr(self.obj, attr),
                    hasattr(self.proxy, attr),
                    "attribute presence mismatch on attr %r and object %r" % (
                        attr, self.obj))

    def test_isinstance(self):
        # NOTE: this method tests the metaclass
        self.assertIsInstance(self.obj, type(self.obj))
        self.assertIsInstance(self.proxy, type(self.obj))

    def test_issubclass(self):
        # NOTE: this method tests the metaclass
        # NOTE: mock doesn't support subclasscheck
        obj = "something other than mock"
        self.assertTrue(issubclass(str, type(obj)))
        self.assertTrue(issubclass(str, type(proxy(obj))))

    def test_class(self):
        self.assertEqual(self.proxy.__class__, self.obj.__class__)
        # NOTE: The proxy cannot hide the fact, that it is a proxy
        self.assertNotEqual(type(self.proxy), type(self.obj))


class proxy_as_class(unittest.TestCase):

    def setUp(self):
        if reality_is_broken:
            print()
            _logger.debug("STARTING")
            _logger.debug("[%s]", self._testMethodName)

    def tearDown(self):
        if reality_is_broken:
            _logger.debug("DONE")

    def test_proxy_subclass(self):
        # NOTE: bring your comb, because this is the extra-hairy land
        class censored(proxy):

            @unproxied
            def __str__(self):
                return "*" * len(super().__str__())
        self.assertTrue(issubclass(censored, proxy))
        self.assertEqual(str(censored("freedom")), "*******")
        self.assertEqual(censored("freedom").__str__(), "*******")
