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
plainbox.abc
===============

Abstract base classes used by checkbox

Those classes are actually implemented in the plainbox.impl package. This
module is here so that the essential API concepts are in a single spot and are
easier to understand (by not being mixed with additional source code).

.. note::

    This module has API stability guarantees. We are not going to break or
    introduce backwards incompatible interfaces here without following our API
    deprecation policy. All existing features will be retained for at least
    three releases. All deprecated symbols will warn when they will cease to be
    available.
"""


from abc import ABCMeta, abstractproperty, abstractmethod


class ITestDefinition(metaclass=ABCMeta):
    """
    Test definition that contains a mixture of meta-data and executable
    information that can be consumed by the test runner to produce results.
    """

    # XXX: All IO methods to save/load this would be in a helper class/function
    # that would also handle format detection, serialization and validation.

    @abstractproperty
    def plugin(self):
        """
        Name of the test data interpreter. Various interpreters are provided by
        the test runner (in association with the user interface).
        """

    @abstractproperty
    def name(self):
        """
        Name of the test
        """

    @abstractproperty
    def requires(self):
        """
        List of expressions that need to be true for this test to be available
        """

    @abstractproperty
    def command(self):
        """
        The shell command to execute to perform the test.

        The return code and standard output / standard error streams will be
        added to the test results automatically.
        """

    @abstractproperty
    def description(self):
        """
        Human-readable description of the test that typically includes the
        steps necessary to perform it.
        """


class ITestResult(metaclass=ABCMeta):
    """
    Object representing test results from a single test run.
    """

    OUTCOME_PASS = 'pass'
    OUTCOME_FAIL = 'fail'
    OUTCOME_SKIP = 'skip'
    # XXX: we could have OUTCOME_UNKNOWN for manual tests if we wish to present
    # that option to the user.

    @abstractproperty
    def test_name(self):
        """
        Name of the test that was invoked
        """
        # XXX: alternatively we could link to the full test definition which
        # would also capture everything that was defined there at the time.

    @abstractproperty
    def outcome(self):
        """
        Outcome of the test

        The result of either automatic or manual verification. Depending on the
        plugin (test type). Available values are defined as class properties
        above.
        """

    @abstractproperty
    def comments(self):
        """
        The comment that was added by the user, if any
        """

    @abstractproperty
    def io_log(self):
        """
        A sequence of tuples (delay, stream-name, data) where delay is the
        delay since the previous message seconds (typically a fractional
        number), stream name is either 'stdout' or 'stderr' and data is the
        bytes object that was obtained from that stream.

        XXX: it could also encode 'stdin' if the user was presented with a
        console to type in and we sent that to the process.

        XXX: This interface is low-level but captures everything that has
        occurred and is text-safe. You can call an utility function to convert
        that to a text string that most closely represents what a user would
        see, having ran this command in the terminal.
        """

    @abstractproperty
    def return_code(self):
        """
        Command return code.

        This is the return code of the process started to execute the command
        from the test definition. It can also encode the signal that the
        process was killed with, if any.
        """

    # XXX: We could also store stuff like test duration and other meta-data
    # but I wanted to avoid polluting this proposal with mundane details


class ITestRunner(metaclass=ABCMeta):
    """
    Something that can run a (test) definition and produce results.

    You can run many tests with one runner, each time you'll get additional
    result object. Typically you will need to connect the runner to a user
    interface but headless mode is also possible.
    """

    @abstractmethod
    def run_test(self, test_definition):
        """
        Run the specified test definition.

        Calling this method may block for arbitrary amount of time. User
        interfaces should ensure that it runs in a separate thread.

        The return value is a TestResult object that contains all the
        data that was captured during the execution of the test.
        """
        # XXX: threads suck, could we make this fully asynchronous? The only
        # thing that we really want is to know when the command has stopped
        # executing. We could expose the underlying process mechanics so that
        # QT/GTK applications could tie that directly into their event loop.


class IUserInterfaceIO:
    """
    Base class that allows test runner to interact with the user interface.
    """

    @abstractmethod
    def get_manual_verification_outcome(self):
        """
        Get the outcome of the manual verification, as according to the user
        May raise NotImplementedError if the user interface cannot provide this
        answer.
        """
