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
:mod:`plainbox.abc` -- abstract base classes
============================================

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


class ITextSource(metaclass=ABCMeta):
    """
    An abstract source of text.

    Concrete instances of this class are used by
    :class:`plainbox.impl.rfc822.Origin` to keep track of where each entry of a
    RFC822-like document came from.
    """


class IJobDefinition(metaclass=ABCMeta):
    """
    Job definition that contains a mixture of meta-data and executable
    information that can be consumed by the job runner to produce results.
    """

    # XXX: All IO methods to save/load this would be in a helper class/function
    # that would also handle format detection, serialization and validation.

    @abstractproperty
    def plugin(self):
        """
        Name of the job interpreter.

        Various interpreters are provided by the job runner.
        """

    @abstractproperty
    def name(self):
        """
        Name of the job
        """

    @abstractproperty
    def requires(self):
        """
        List of expressions that need to be true for this job to be available

        This value can be None
        """

    @abstractproperty
    def command(self):
        """
        The shell command to execute to perform the job.

        The return code, standard output and standard error streams are
        automatically recorded and processed, depending on the plugin type.

        This value can be None
        """

    @abstractproperty
    def description(self):
        """
        Human-readable description of the job.

        This field is typically used to include execution and verification
        steps for manual and human-assisted tests.

        This value can be None
        """

    @abstractproperty
    def depends(self):
        """
        Comma-delimited dependency expression

        This field can be used to express job dependencies. If a job depends on
        another job it can only start if the other job had ran and succeeded.

        This is the original data as provided when constructed. Use
        get_direct_dependencies() to obtain the parsed equivalent.

        This value can be None
        """


class IJobResult(metaclass=ABCMeta):
    """
    Class for representing results from a single job
    """

    # XXX: We could also store stuff like job duration and other meta-data but
    # I wanted to avoid polluting this proposal with mundane details

    # The outcome of a job is a one-word classification how how it ran.  There
    # are several values that were not used in the original implementation but
    # their existence helps to organize and implement plainbox. They are
    # discussed below to make their intended meaning more detailed than is
    # possible from the variable name alone.
    #
    # The None outcome - a job that basically did not run at all.
    OUTCOME_NONE = None
    # The pass and fail outcomes are the two most essential, and externally
    # visible, job outcomes. They can be provided by either automated or manual
    # "classifier" - a script or a person that clicks a "pass" or "fail"
    # button.
    OUTCOME_PASS = 'pass'
    OUTCOME_FAIL = 'fail'
    # The skip outcome is used when the operator selected a job but then
    # skipped it. This is typically used for a manual job that is tedious or
    # was selected by accident.
    OUTCOME_SKIP = 'skip'
    # The not supported outcome is used when a job was about to run but a
    # dependency or resource requirement prevent it from running.  XXX: perhaps
    # this should be called "not available", not supported has the "unsupported
    # code" feeling associated with it.
    OUTCOME_NOT_SUPPORTED = 'not-supported'
    # A temporary state that should be removed later on, used to indicate that
    # job runner is not implemented but the job "ran" so to speak.
    OUTCOME_NOT_IMPLEMENTED = 'not-implemented'
    # A temporary state before the user decides on the outcome of a manual
    # job or any other job that requires manual verification
    OUTCOME_UNDECIDED = 'undecided'

    # List of all valid values of OUTCOME_xxx
    ALL_OUTCOME_LIST = [
        OUTCOME_NONE,
        OUTCOME_PASS,
        OUTCOME_FAIL,
        OUTCOME_SKIP,
        OUTCOME_NOT_SUPPORTED,
        OUTCOME_NOT_IMPLEMENTED,
        OUTCOME_UNDECIDED,
    ]

    @abstractproperty
    def outcome(self):
        """
        Outcome of the test.

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
        """
        # XXX: it could also encode 'stdin' if the user was presented with a
        # console to type in and we sent that to the process.

        # XXX: This interface is low-level but captures everything that has
        # occurred and is text-safe. You can call an utility function to
        # convert that to a text string that most closely represents what a
        # user would see, having ran this command in the terminal.

    @abstractproperty
    def return_code(self):
        """
        Command return code.

        This is the return code of the process started to execute the command
        from the job definition. It can also encode the signal that the
        process was killed with, if any.
        """

    @abstractmethod
    def get_io_log(self):
        """
        Compute and return the sequence of IOLogRecord objects.

        :returns:
            A sequence of tuples (delay, stream-name, data) where delay is the
            delay since the previous message seconds (typically a fractional
            number), stream name is either 'stdout' or 'stderr' and data is the
            bytes object that was obtained from that stream.
        """


class IJobQualifier(metaclass=ABCMeta):
    """
    An opaque qualifier for a job definition.

    This is an abstraction for matching jobs definitions to names, patterns and
    other means of selecting jobs.
    """

    @abstractmethod
    def designates(self, job):
        """
        Check if this qualifier designates the specified
        :class:`plainbox.abc.IJobDefinition`

        :returns True: if the qualifier designates the specified job
        :returns False: otherwise
        """


class IJobRunner(metaclass=ABCMeta):
    """
    Something that can run a job definition and produce results.

    You can run many jobs with one runner, each time you'll get additional
    result object. Typically you will need to connect the runner to a user
    interface but headless mode is also possible.
    """

    @abstractmethod
    def run_job(self, job):
        """
        Run the specified job.

        Calling this method may block for arbitrary amount of time. User
        interfaces should ensure that it runs in a separate thread.

        The return value is a JobResult object that contains all the data that
        was captured during the execution of the job. Some jobs may not return
        a JobResult value.
        """
        # XXX: threads suck, could we make this fully asynchronous? The only
        # thing that we really want is to know when the command has stopped
        # executing. We could expose the underlying process mechanics so that
        # QT/GTK applications could tie that directly into their event loop.


class IUserInterfaceIO(metaclass=ABCMeta):
    """
    Base class that allows job runner to interact with the user interface.
    """

    @abstractmethod
    def get_manual_verification_outcome(self):
        """
        Get the outcome of the manual verification, as according to the user
        May raise NotImplementedError if the user interface cannot provide this
        answer.
        """


class IProviderBackend1(metaclass=ABCMeta):
    """
    Provider for the current type of tests.

    This class provides the APIs required by the internal implementation
    that are not considered normal public APIs. The only consumer of the
    those methods and properties are internal to plainbox.
    """

    @abstractproperty
    def CHECKBOX_SHARE(self):
        """
        Return the required value of CHECKBOX_SHARE environment variable.

        .. note::
            This variable is only required by one script.
            It would be nice to remove this later on.
        """

    @abstractproperty
    def extra_PYTHONPATH(self):
        """
        Return additional entry for PYTHONPATH, if needed.

        This entry is required for CheckBox scripts to import the correct
        CheckBox python libraries.

        .. note::
            The result may be None
        """

    @abstractproperty
    def bin_dir(self):
        """
        directory where all the executables needed by this provider reside
        """

    @abstractproperty
    def secure(self):
        """
        flag indicating that this provider was loaded from the secure portion
        of PROVIDERPATH and thus can be used with the
        plainbox-trusted-launcher-1.
        """


class IProvider1(metaclass=ABCMeta):
    """
    Provider for the current type of tests

    Also known as the 'checkbox-like' provider.
    """

    @abstractproperty
    def name(self):
        """
        name of this provider

        This name should be dbus-friendly. It should not be localizable.
        """

    @abstractproperty
    def description(self):
        """
        description of this providr

        This name should be dbus-friendly. It should not be localizable.
        """

    @abstractmethod
    def get_builtin_jobs(self):
        """
        Load all the built-in jobs and return them
        """

    @abstractmethod
    def get_builtin_whitelists(self):
        """
        Load all the built-in whitelists and return them
        """


class ISessionStateController(metaclass=ABCMeta):
    """
    Interface for session state controller classes.

    Session state controller classes cooperate with
    :class:`~plainbox.impl.session.state.SessionState` and
    :class:`~plainbox.impl.depmgr.DependencySolver` classes and implement
    knowledge unique to particular job semantics. Before execution the
    controller can influence job runnability (by setting inhibitors). After
    execution the controller can observe the result and influence session state
    """

    @abstractmethod
    def get_dependency_set(self, job):
        """
        Get the set of direct dependencies of a particular job.

        :param job:
            A IJobDefinition instance that is to be visited
        :returns:
            set of pairs (dep_type, job_name)

        Returns a set of pairs (dep_type, job_name) that describe all
        dependencies of the specified job. The first element in the pair,
        dep_type, is either DEP_TYPE_DIRECT or DEP_TYPE_RESOURCE. The second
        element is the name of the job.
        """

    @abstractmethod
    def get_inhibitor_list(self, session_state, job):
        """
        Get a list of readiness inhibitors that inhibit a particular job.

        :param session_state:
            A SessionState instance that is used to interrogate the
            state of the session where it matters for a particular
            job. Currently this is used to access resources and job
            results.
        :param job:
            A JobDefinition instance
        :returns:
            List of JobReadinessInhibitor
        """

    @abstractmethod
    def observe_result(self, session_state, job, result):
        """
        Notice the specified test result and update readiness state.

        :param session_state:
            A SessionState object
        :param job:
            A JobDefinition object
        :param result:
            A IJobResult object

        This function updates the internal result collection with the data from
        the specified test result. Results can safely override older results.
        Results also change the ready map (jobs that can run) because of
        dependency relations.
        """


class IExecutionController(metaclass=ABCMeta):
    """
    Interface for job execution controller clases.

    Execution controllers encapsulate knowledge on how to run command
    associated with a particular job. Some executors might run the command
    directly, others might delegate the task to a helper program or perform
    some special-cased customization to the execution environment.
    """

    @abstractmethod
    def execute_job(self, job, config, extcmd_popen):
        """
        Execute the specified job using the specified subprocess-like object

        :param job:
            The JobDefinition to execute
        :param config:
            A PlainBoxConfig instance which can be used to load missing
            environment definitions that apply to all jobs. It is used to
            provide values for missing environment variables that are required
            by the job (as expressed by the environ key in the job definition
            file).
        :param extcmd_popen:
            A subprocess.Popen like object
        :returns:
            The return code of the command, as returned by subprocess.call()
        """

    @abstractmethod
    def get_score(self, job):
        """
        Compute how applicable this controller is for the specified job.

        :returns:
            A numeric score, or None if the controller cannot run this job.
            The higher the value, the more applicable this controller is.
        """
