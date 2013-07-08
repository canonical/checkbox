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
:mod:`plainbox.testing_utils.testcases` -- additional TestCase classes
======================================================================

Implementation of additional TestCase classes that aid in testing.
"""

from unittest import TestCase
from unittest.util import strclass


def load_tests(loader, suite, pattern):
    # Because of the default patterns used to discover test cases
    # we need to prevent the unittest machinery from treating the
    # TestCase* classes as actual tests.
    #
    # The discovery mechanism has little-known feature whereas the discovery
    # can be customized on a per-package and per-module level by defining the
    # load_tests() function. This function must return a TestSuite object
    #
    # Here we simply return an empty suite.
    return loader.suiteClass([])


# Treat this as a part of TestCase implementation detail, removing it from the
# tracebacks that are reported to the developer.
__unittest = True


class TestCaseParameters:
    """
    Class for holding test case parameters

    Instances of this class are provided as the .parameters attribute to
    instances of TestCaseWithParameters during run().

    The class supports attribute lookup so tests can be written in convenient
    form. Having a test case with parameters 'foo' and 'bar' they can be
    accessed as self.parameters.foo and self.parameters.bar respectively.
    """

    __slots__ = ('_names', '_values')

    def __init__(self, names, values):
        """
        Initialize with a tuple of parameter names and values.
        Both arguments have to be tuples.
        """
        self._names = names
        self._values = values

    def __eq__(self, other):
        if not isinstance(other, TestCaseParameters):
            return NotImplemented
        return (self._names == other._names
                and self._values == other._values)

    def __getattr__(self, attr):
        try:
            return self._values[self._names.index(attr)]
        except (ValueError, LookupError):
            # index() raises ValueError
            # [] raises LookupError subclass
            raise AttributeError(attr)

    def __str__(self):
        return ", ".join([
            "{}: {}".format(name, value)
            for name, value in zip(self._names, self._values)])

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, str(self))


class TestCaseWithParameters(TestCase):
    """
    TestCase parametrized by any number of named parameters.

    This class can save a lot of typing or creating dummy base classes and
    other implementation tricks that aim to reduce duplication in code that
    tests multiple values of a parameter.

    For all intents and purposes this is just a standard TestClass instance,
    what makes it different are the few tricks employed to make it appear as a
    collection of test cases instead.

    Each TestCase created from the test_** methods will be invoked for all the
    parameter values. Any number of parameters that can be provided. A tuple of
    values must be provided for each parameter.

    In simple cases the developer only needs to provide two class attributes,
    parameter_names and parameter_values. In more complex cases behavior can be
    customized by defining two class methods, get_parameter_names() and
    get_parameter_values(). Note that you _must_ define a non-empty list of
    parameter values, otherwise this test will behave as if it never existed
    (analogous how multiplication by zero works).

    .. note::
        Technical note for tinkerers and subclass authors. Python unittest
        framework is pretty annoying to work with or extend. In practice you
        should always keep the source code (of a particular python version)
        open to reason about it.

        Parametrization is implemented by creating additional instances of
        TestCaseWithParameters with immutable, bound, parameters. That logic is
        implemented in run(). The multiplication of TestCase instances happens
        in _parametrize(). If your sub-class needs to do something special
        there you might need to override it.

        Ideally the unittest framework could allow customizing discovery in a
        standard way. If that were true then we could instantiate parametrized
        copies early and then let the normal run() mechanics work. Sadly this
        is not the case.

        Most special python methods also had to be overridden to take account
        of the new _parameters instance attribute. This includes __str__(),
        __repr__(), __eq__() and __hash__().

        Additional methods unique to unittest framework were implemented to
        convey the value of the parameter back to the user / developer. Those
        include id() and countTestCases()
    """

    def __init__(self, methodName="runTest", parameters=None):
        """
        Overridden method of TestCase

        Instantiates a new TestCase that will run a given method. By default
        creates the 'unparameterized' version which spawns real test cases
        (with the bound parameter) when .run() is called.
        """
        super(TestCaseWithParameters, self).__init__(methodName)
        self._parameters = parameters

    @property
    def parameters(self):
        """
        Return the value of parameters that specialize this test case

        Normal instances always return None here, the special, parametrized,
        instance that is constructed once for each parameter value during
        run() (where testing actually happens), returns the real value.
        """
        return self._parameters

    parameter_names = ()

    @classmethod
    def get_parameter_names(cls):
        """
        Return a tuple of parameters that affect this test case.
        """
        return cls.parameter_names

    parameter_values = ()

    @classmethod
    def get_parameter_values(cls):
        """
        Return a tuple of tuple of values that should be mapped to subsequent
        attributes named, as returned by get_parameter_names()
        """
        return cls.parameter_values

    def _parametrize(self, parameters):
        """
        Internal implementation method of TestCaseWithParameters.

        Creates a new instance of the sub-class that is about to be tested
        binding the particular value of the parameters supplied. This is
        where test cases are actually instantiated / multiplied.
        """
        return type(self)(self._testMethodName, parameters)

    def countTestCases(self):
        """
        Overridden method of unittest.TestCase()

        Behaves different depending on whether it is called on the original
        instance or the parametrized instance. The original instance
        behaves like a TestSuite, returning the number of parameter values.

        Each parametrized instance (created with _parametrize()) returns 1
        """
        if self.parameters is None:
            return len(self.get_parameter_values())
        else:
            return 1

    def run(self, result=None):
        """
        Overridden version of TestCase.run()

        Creates additional instances of the class being tested, one for each
        value returned by get_parameter_values() by calling _parametrize().

        Each of the parametrized instances is tested normally.
        """
        # Get a result object if we don't have one
        if result is None:
            result = self.defaultTestResult()
        # Get the list of parameter names
        names = self.get_parameter_names()
        # For each list of parameter values:
        for values in self.get_parameter_values():
            # Construct the parameter placeholder
            parameters = TestCaseParameters(names, values)
            # Construct a parametrized version of this test case
            parametrized_test_case = self._parametrize(parameters)
            # Super-call the run() method of the new instance
            super(TestCaseWithParameters, parametrized_test_case).run(result)

    def id(self):
        """
        Overridden version of TestCase.id()

        This is an internal implementation detail of TestCase, it is used in
        certain places instead of __str__(). It behaves very similar to what
        __str__() does, except that it displays the class name differently
        """
        if self.parameters is None:
            return "{}.{} [<unparameterized>]".format(
                strclass(self.__class__), self._testMethodName)
        else:
            return "{}.{} [{}]".format(
                strclass(self.__class__), self._testMethodName,
                self.parameters)

    def __str__(self):
        """
        Overridden version of TestCase.__str__()

        This version takes the current value of parameters into account. During
        testing in run(), when parameters are not None, they are added to the
        value returned by the superclass. At other times the string
        <unparameterized> is used.
        """
        if self.parameters is None:
            return "{} [<unparameterized>]".format(
                super(TestCaseWithParameters, self).__str__())
        else:
            return "{} [{}]".format(
                super(TestCaseWithParameters, self).__str__(),
                self.parameters)

    def __repr__(self):
        """
        Overridden version of TestCase.__repr__()

        This version displays the value of the parameters attribute
        """
        return "<{} testMethod={} parameters={!r}>".format(
            strclass(self.__class__), self._testMethodName,
            self.parameters)

    def __eq__(self, other):
        """
        Overridden version of TestCase.__eq__()

        This version also compares the parameters attribute
        """
        if not isinstance(other, TestCaseWithParameters):
            return NotImplemented
        return (self._testMethodName == other._testMethodName
                and self._parameters == other.parameters)

    def __hash__(self):
        """
        Overridden version of TestCase.__hash__()

        This version also uses the parameters attribute
        """
        return hash((type(self), self._testMethodName, self._parameters))
