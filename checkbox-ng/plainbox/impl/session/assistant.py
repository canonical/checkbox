# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

"""Session Assistant."""

import collections
import datetime
import fnmatch
import io
import itertools
import logging
import os
import time

from plainbox.abc import IJobResult
from plainbox.abc import IJobRunnerUI
from plainbox.abc import ISessionStateTransport
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.decorators import raises
from plainbox.impl.developer import UnexpectedMethodCall
from plainbox.impl.developer import UsageExpectation
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import JobRunnerUIDelegate
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session.storage import SessionStorageRepository
from plainbox.impl.transport import CertificationTransport
from plainbox.impl.transport import TransportError
from plainbox.public import get_providers
from plainbox.vendor import morris

_logger = logging.getLogger("plainbox.session.assistant")


__all__ = ('SessionAssistant', )

ResumeCandidate = collections.namedtuple('ResumeCandidate', ['id', 'metadata'])


class SessionAssistant:

    """
    Assisting class to simplify common testing scenarios.

    The assistant acts as a middle-man between the session manager and the
    application. It handles all currently known stages of the testing
    work-flow.

    .. note::
        The assistant class assumes single-threaded applications. Classic event
        loop or threaded applications can be developed with a little bit of
        care. The main problem is that plainbox doesn't support event loops
        yet.  Certain blocking operations (running jobs mostly) need to be done
        from another thread. It is recommended to run all of plainbox in a
        thread (either python or native thread embedding python runtime)

    A typical application flow will look like this:

    * The application calls :meth:`__init__()` to create a new session
      assistant object with its own identifier as the only argument. This lets
      multiple programs that use the plainbox APIs co-exists without clashes.
    * (optionally) The application can call :meth:`use_alternate_repository()`
      to change the location of the session storage repository. This is where
      various files are created so if you don't want to use the default
      location for any reason this is the only chance you have.
    * The application selects a set of providers to load using
      :meth:`select_providers()`. Typically applications will work with a
      well-defined set of providers, either maintained by the same set of
      developers or (sometimes) by reusing some third party test providers.
      A small set of wild-cards are supported so that applications can load all
      providers from a given name-space or even all available providers.
    """

    # TODO: create a flowchart of possible states

    def __init__(self, app_id):
        """
        Initialize a new session assistant.

        :param app_id:
            Identifier of the testing application. The identifier should be
            unique and constant throughout the support cycle of the
            application.

        The application identifier is useful to implement session resume
        functionality where the application can easily filter out sessions from
        other programs.
        """
        self._app_id = app_id
        self._repo = SessionStorageRepository()
        self._config = PlainBoxConfig().get()
        self._execution_ctrl_list = None  # None is "default"
        # List of providers that were selected. This is buffered until a
        # session is created or resumed.
        self._selected_providers = []
        # All the key state for the active session. Technically just the
        # manager matters, the context and metadata are just shortcuts to stuff
        # available on the manager.
        self._manager = None
        self._context = None
        self._metadata = None
        self._runner = None
        # Expect that select_providers() be called
        UsageExpectation.of(self).allowed_calls = {
            self.use_alternate_repository: (
                "use an alternate storage repository"),
            self.use_alternate_configuration: (
                "use an alternate configuration system"),
            self.use_alternate_execution_controllers: (
                "use an alternate execution controllers"),
            self.select_providers: (
                "select the providers to work with"),
            self.get_canonical_certification_transport: (
                "create a transport for the C3 system"),
            self.get_canonical_hexr_transport: (
                "create a transport for the HEXR system"),
        }

    @raises(UnexpectedMethodCall)
    def use_alternate_repository(self, pathname: str) -> None:
        """
        Setup an alternate location for the session storage repository.

        :param pathname:
            Directory name (that is created on demand) where sessions are
            supposed to be stored.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be used to use a non-standard repository location. This
        is useful for testing, where it is good to separate test sessions from
        any real data that the user may be using.

        On some platforms, this can be also used to use a better default
        location. If you have to call this in your application then please open
        a bug. Plainbox should integrate with all the platforms correctly out
        of the box.
        """
        UsageExpectation.of(self).enforce()
        self._repo = SessionStorageRepository(pathname)
        _logger.debug("Using alternate repository: %r", pathname)
        # NOTE: We expect applications to call this at most once.
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_repository]

    @raises(UnexpectedMethodCall)
    def use_alternate_configuration(self, config):
        """
        Use alternate configuration object.

        :param config:
            A configuration object that implements a superset of the plainbox
            configuration.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            Please check the source code to understand which values to pass
            here. This method is currently experimental.
        """
        UsageExpectation.of(self).enforce()
        self._config = config
        # NOTE: We expect applications to call this at most once.
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_configuration]

    @raises(UnexpectedMethodCall)
    def use_alternate_execution_controllers(
        self, ctrl_list: 'List[IExecutionController]'
    ) -> None:
        """
        Use alternate execution controllers.

        :param ctrl_list:
            The list of execution controllers to use.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be used to use any custom execution controllers to
        execute jobs. Normally those should be offered by the
        ``SessionDeviceContext`` (which is a part of the implementation) and
        they should be _good_ for any use but as we learned some applications
        needed to offer alternate controllers.

        .. note::
            Please check the source code to understand which values to pass
            here. This method is currently experimental.
        """
        UsageExpectation.of(self).enforce()
        self._ctrl_list = ctrl_list
        # NOTE: We expect applications to call this at most once.
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_execution_controllers]

    @raises(ValueError, UnexpectedMethodCall)
    def select_providers(
        self, *patterns, additional_providers: 'Iterable[Provider1]'=()
    ) -> 'List[Provider1]':
        """
        Load plainbox providers.

        :param patterns:
            The list of patterns (or just names) of providers to load.

            Note that some special provides are always loaded, regardless of if
            the application wants that or not. Those providers are a part of
            plainbox itself and are required for normal operation of the
            framework.

            The names may include the ``*`` character (asterisk) to indicate
            "any". This includes both the namespace part and the provider name
            part, e.g. ``2013.com.canonical.certification::*`` will load all of
            providers made by the Canonical certification team.  To load
            everything just pass ``*``.
        :param additional_providers:
            A list of providers that were loaded by other means (usually in
            some app-custom way).
        :returns:
            The list of loaded providers (including plainbox providers)
        :raises ValueError:
            If any of the patterns didn't match any provider.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        Providers are loaded into a temporary area so that they are ready for a
        session that you can either create from scratch or resume one you may
        have created earlier. In either case, this is the first method you
        should call.

        A provider is used to supply tests (or in general, jobs) to execute.
        Typically applications will have an associated, well-known provider
        that they wish to load.

        Providers can be broken and can, in fact, load in a partially or
        entirely damaged state. Applications should inspect the problem list of
        each loaded provider to see if they wish to abort.

        .. todo::
            Delegate correctness checking to a mediator class that also
            implements some useful, default behavior for this.
        """
        UsageExpectation.of(self).enforce()
        # NOTE: providers are actually enumerated here, they are only loaded
        # and validated on demand so this is is not going to expose any
        # problems from utterly broken providers we don't care about.
        provider_list = get_providers()
        # NOTE: copy the list as we don't want to mutate the object returned by
        # get_providers().  This helps unit tests that actually return a fixed
        # list here.
        provider_list = provider_list[:] + list(additional_providers)
        # Select all of the plainbox providers in a separate iteration. This
        # way they get loaded unconditionally, regardless of what patterns are
        # passed to the function (including not passing *any* patterns).
        for provider in provider_list[:]:
            if provider.namespace == "2013.com.canonical.plainbox":
                provider_list.remove(provider)
                self._selected_providers.append(provider)
                self.provider_selected(provider, auto=True)
        # Select all of the providers matched by any of the patterns.
        for pat in patterns:
            # Track useless patterns so that we can report them
            useless = True
            for provider in provider_list[:]:
                if (provider.name == pat or
                        fnmatch.fnmatchcase(provider.name, pat)):
                    # Once a provider is selected, remove it from the list of
                    # candidates. This saves us from checking if we're adding
                    # something twice at each iteration.
                    provider_list.remove(provider)
                    self._selected_providers.append(provider)
                    self.provider_selected(provider, auto=False)
                    useless = False
            if useless:
                raise ValueError("nothing selected with: {}".format(pat))
        # Set expectations for subsequent calls.
        allowed_calls = UsageExpectation.of(self).allowed_calls
        del allowed_calls[self.select_providers]
        allowed_calls[self.start_new_session] = (
            "create a new session from scratch")
        allowed_calls[self.get_resumable_sessions] = (
            "get resume candidates")
        return self._selected_providers

    @morris.signal
    def provider_selected(self, provider, auto):
        """
        Signal fired when a provider is loaded.

        :param provider:
            The provider object that was loaded.
        :param auto:
            Flag indicating if the provider was loaded automatically by the
            framework or explicitly by the application.

        This signal is fired after a provider is loaded and added to the
        session. It can be safely ignored but applications may wish to use this
        to show some UI element.
        """
        _logger.debug("Provider selected: %r", provider)

    @raises(UnexpectedMethodCall)
    def start_new_session(self, title: str):
        """
        Create a new testing session.

        :param title:
            Title of the session.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be used to create a new session. This will create some
        filesystem entries related to the session.

        The session title should be a human-readable string, as much as the
        application can create one, that describes the goal of the session.
        Some user interfaces will display this information.

        Using this method always creates a _new_ session. If the application
        intends to use session resuming functionality it should use other
        methods to see if session should be resumed instead.
        """
        UsageExpectation.of(self).enforce()
        self._manager = SessionManager.create(self._repo)
        self._context = self._manager.add_local_device_context()
        for provider in self._selected_providers:
            self._context.add_provider(provider)
        self._metadata = self._context.state.metadata
        self._metadata.app_id = self._app_id
        self._metadata.title = title
        self._metadata.flags = {'bootstrapping'}
        self._manager.checkpoint()
        self._command_io_delegate = JobRunnerUIDelegate(_SilentUI())
        self._runner = JobRunner(
            self._manager.storage.location,
            self._context.provider_list,
            jobs_io_log_dir=os.path.join(
                self._manager.storage.location, 'io-logs'),
            command_io_delegate=self._command_io_delegate,
            execution_ctrl_list=self._execution_ctrl_list)
        self.session_available(self._manager.storage.id)
        _logger.debug("New session created: %s", title)
        UsageExpectation.of(self).allowed_calls = {
            self.get_test_plans: "to get the list of available test plans",
            self.get_test_plan: "to get particular test plan object",
            self.select_test_plan: "select the test plan to execute",
            self.get_session_id: "to get the id of currently running session",
            self.get_session_dir: ("to get the path where current session is"
                                   "stored"),
        }

    @raises(KeyError, UnexpectedMethodCall)
    def resume_session(self, session_id: str) -> 'SessionMetaData':
        """
        Resume a session.

        :param session_id:
            The identifier of the session to resume.
        :returns:
            Resumed session metadata.
        :raises KeyError:
            If the session with a given session_id cannot be found.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method restores internal state of the plainbox runtime as it was
        the last time session assistant did a checkpoint, i.e. session
        assistant's clients commited any information (e.g. saves job result,
        runs bootstrapping, updates app blob, etc.)
        """
        UsageExpectation.of(self).enforce()
        all_units = list(itertools.chain(
            *[p.unit_list for p in self._selected_providers]))
        self._manager = SessionManager.load_session(
            all_units, self._resume_candidates[session_id][0])
        self._context = self._manager.default_device_context
        self._metadata = self._context.state.metadata
        self._command_io_delegate = JobRunnerUIDelegate(_SilentUI())
        self._runner = JobRunner(
            self._manager.storage.location,
            self._context.provider_list,
            jobs_io_log_dir=os.path.join(
                self._manager.storage.location, 'io-logs'),
            command_io_delegate=self._command_io_delegate,
            execution_ctrl_list=self._execution_ctrl_list)
        self.session_available(self._manager.storage.id)
        _logger.debug("Session resumed: %s", session_id)
        UsageExpectation.of(self).allowed_calls = {
            self.select_test_plan: "to save test plan selection",
        }
        return self._resume_candidates[session_id][1]

    @raises(UnexpectedMethodCall)
    def get_resumable_sessions(self) -> 'Tuple[str, SessionMetaData]':
        """
        Check repository for sessions that could be resumed.

        :returns:
            A generator that yields namedtuples with (id, metadata) of
            subsequent resumable sessions, starting from the youngest one.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method iterates through incomplete sessions saved in the storage
        repository and looks for the ones that were created using the same
        app_id as the one currently used.

        Applications can use sessions' metadata (and the app_blob contained
        in them) to decide which session is the best one to propose resuming.
        """
        UsageExpectation.of(self).enforce()
        # let's keep resume_candidates, so we don't have to load data again
        self._resume_candidates = {}
        for storage in self._repo.get_storage_list():
            data = storage.load_checkpoint()
            if len(data) == 0:
                continue
            try:
                metadata = SessionPeekHelper().peek(data)
            except SessionResumeError:
                _logger.info("Exception raised when trying to resume"
                             "session: %s", str(storage.id))
            else:
                if (metadata.app_id == self._app_id and
                        SessionMetaData.FLAG_INCOMPLETE in metadata.flags):
                    candidate = ResumeCandidate(storage.id, metadata)
                    self._resume_candidates[storage.id] = (storage, metadata)
                    UsageExpectation.of(self).allowed_calls[
                        self.resume_session] = "resume session"
                    yield candidate

    def update_app_blob(self, app_blob: bytes) -> None:
        """
        Update custom app data and save the session in the session storage.

        :param app_blob:
            Bytes sequence containing JSON-ised app_blob object.

        """
        self._context.state.metadata.app_blob = app_blob
        self._manager.checkpoint()

    @morris.signal
    def session_available(self, session_id):
        """
        Signal sent when a session is available.

        :param session_id:
            Identifier of the session. This identifier is randomly generated
            and allocated by plainbox, you cannot influence it.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        The identifier is persistent. You can use it to resume the session
        later. Certain tools will allow the user to operate on a session as
        long as the identifier is known. You can use this signal to obtain this
        identifier.

        .. note::
            The identifier is unique within the storage repository. If you made
            use of :meth:`use_alternate_repository() then please keep this in
            mind.
        """
        _logger.debug("Session is now available: %s", session_id)

    @raises(UnexpectedMethodCall)
    def get_session_id(self):
        """
        Get the identifier of the session.

        :returns:
            The string that identifies the session in the repository being
            used. The identifier is a short, random directory name (without the
            full path), relative to the session storage repository.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        Applications can use this method and some side-channel to remember the
        session that was executed most recently. This can be useful in resuming
        that session without the need to search and analyze all of the sessions
        in the repository.
        """
        UsageExpectation.of(self).enforce()
        return self._manager.storage.id

    @raises(UnexpectedMethodCall)
    def get_session_dir(self):
        """
        Get the pathname of the session directory.

        :returns:
            The string that represents the absolute pathname of the session
            directory. All of the files and directories inside that directory
            constitute session state.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            The layout of the session is documented but is considered volatile
            at this stage. The only thing that can be done reliably is a
            complete archive (backup) of the directory. This is guaranteed to
            work.
        """
        UsageExpectation.of(self).enforce()
        return self._manager.storage.location

    @raises(UnexpectedMethodCall)
    def get_test_plans(self) -> 'List[str]':
        """
        Get a set of test plan identifiers.

        :returns:
            A list of test plan identifiers.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method computes the set of category identifiers that contains each
        category for which at least test might be executed in this session.
        This set does not include bootstrap jobs as they must be executed prior
        to actually allowing the user to know what jobs are available.
        """
        UsageExpectation.of(self).enforce()
        return [unit.id for unit in self._context.unit_list
                if unit.Meta.name == 'test plan']

    @raises(KeyError, UnexpectedMethodCall)
    def select_test_plan(self, test_plan_id):
        """
        Select a test plan for execution.

        :param test_plan_id:
            The identifier of the test plan to execute.
        :raises KeyError:
            If the test plan with that identifier cannot be found.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        Test plans describe all of the essential details needed to execute a
        set of tests. Like other plainbox components each test plan has an
        unique identifier.

        Upon making the selection the application can inspect the execution
        plan which is expressed as a list of jobs to execute.
        """
        UsageExpectation.of(self).enforce()
        test_plan = self._context.get_unit(test_plan_id, 'test plan')
        self._manager.test_plans = (test_plan, )
        if False:
            """
            desired_job_list = select_jobs(
                self._context.state.job_list, [unit.get_qualifier()])
            self._context.state.update_desired_job_list(desired_job_list)
            self._metadata.flags = {'incomplete'}
            """
        self._manager.checkpoint()
        UsageExpectation.of(self).allowed_calls = {
            self.bootstrap: "to run the bootstrap process"
        }

    @raises(UnexpectedMethodCall)
    def bootstrap(self):
        """
        Perform session bootstrap process to discover all content.

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        The session assistant offers two mechanism for generating additional
        content (primarily jobs). Understanding this mechanism is important for
        applications that wish to display a list of jobs before the test
        operator finally commits to running a subset of them.

        During the bootstrap phase resource jobs that are associated with job
        templates may generate new jobs according to the information specified
        in the template. In addition, local jobs can generate arbitrary
        (unrestricted) units. Both of those mechanism are subject to the
        validation system (invalid units are discarded).

        When this method returns (which can take a while) the session is now
        ready for running any jobs.

        .. warning:
            This method will not return until the bootstrap process is
            finished. This can take any amount of time (easily over one minute)
        """
        UsageExpectation.of(self).enforce()
        # NOTE: there is next-to-none UI here as bootstrap jobs are limited to
        # just resource and local jobs (including their dependencies) so there
        # should be very little UI required.
        desired_job_list = select_jobs(
            self._context.state.job_list,
            [plan.get_bootstrap_qualifier() for plan in (
                self._manager.test_plans)])
        self._context.state.update_desired_job_list(desired_job_list)
        for job in self._context.state.run_list:
            UsageExpectation.of(self).allowed_calls[self.run_job] = (
                "to run bootstrapping job")
            rb = self.run_job(job.id, 'silent', False)
            self.use_job_result(job.id, rb.get_result())
        # Perform initial selection -- we want to run everything that is
        # described by the test plan that was selected earlier.
        desired_job_list = select_jobs(
            self._context.state.job_list,
            [plan.get_qualifier() for plan in self._manager.test_plans])
        self._context.state.update_desired_job_list(desired_job_list)
        # Set subsequent usage expectations i.e. all of the runtime parts are
        # available now.
        UsageExpectation.of(self).allowed_calls = (
            self._get_allowed_calls_in_normal_state())
        self._metadata.flags = {'incomplete'}
        self._manager.checkpoint()

    @raises(KeyError, UnexpectedMethodCall)
    def use_alternate_selection(self, selection: 'Iterable[str]'):
        """
        Setup an alternate set of jobs to run.

        :param selection:
            A sequence of identifiers of jobs that the user would like to run.
        :raises KeyError:
            If the selection refers to unknown jobs.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be called at any time to change the _selection_ of jobs
        that the user wishes to run. Any job present in the session can be
        used.

        By default, after selecting a test plan, the job selection includes all
        of the jobs described by that test plan.

        .. note::
            Calling this method will alter the result of
            :meth:`get_static_todo_list()` and :meth:`get_dynamic_todo_list()`.
        """
        UsageExpectation.of(self).enforce()
        desired_job_list = [
            self._context.get_unit(job_id, 'job') for job_id in selection]
        self._context.state.update_desired_job_list(desired_job_list)

    @raises(UnexpectedMethodCall)
    def filter_jobs_by_categories(self, categories: 'Iterable[str]'):
        """
        Filter out jobs with categories that don't match given ones.

        :param categories:
            A sequence of category identifiers of jobs that should stay in the
            todo list.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be called at any time to unselect jobs that belong to
        a category not present in `categories`.

        .. note::
            Calling this method will alter the result of
            :meth:`get_static_todo_list()` and :meth:`get_dynamic_todo_list()`.
        """
        UsageExpectation.of(self).enforce()
        selection = [job.id for job in [
            self.get_job(job_id) for job_id in self.get_static_todo_list()] if
            job.category_id in categories]
        self.use_alternate_selection(selection)

    @raises(UnexpectedMethodCall)
    def remove_all_filters(self):
        """
        Bring back original job list.

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be called to remove all filters applied from currently
        reigning job selection.
        """
        UsageExpectation.of(self).enforce()
        desired_job_list = select_jobs(
            self._context.state.job_list,
            [plan.get_qualifier() for plan in self._manager.test_plans])
        self._context.state.update_desired_job_list(desired_job_list)


    @raises(KeyError, UnexpectedMethodCall)
    def get_job_state(self, job_id: str) -> 'JobState':
        """
        Get the mutable state of the job with the given identifier.

        :returns:
            The JobState object that corresponds to the given identifier.
        :raises KeyError:
            If no such job exists
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            The returned object contains parts that may not be covered by the
            public api stability promise. Refer to the documentation of the
            JobState class for details.
        """
        UsageExpectation.of(self).enforce()
        # XXX: job_state_map is a bit low level, can we avoid that?
        return self._context.state.job_state_map[job_id]

    @raises(KeyError, UnexpectedMethodCall)
    def get_job(self, job_id):
        """
        Get the definition of the job with the given identifier.

        :returns:
            The JobDefinition object that corresponds to the given identifier.
        :raises KeyError:
            If no such job exists
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            The returned object contains parts that may not be covered by the
            public api stability promise. Refer to the documentation of the
            JobDefinition class for details.
        """
        UsageExpectation.of(self).enforce()
        # we may want to decide early about the result of the job, without
        # running it (e.g. when skipping the job)
        allowed_calls = UsageExpectation.of(self).allowed_calls
        allowed_calls[self.use_job_result] = "remember the result of this job"
        return self._context.get_unit(job_id, 'job')

    @raises(KeyError, UnexpectedMethodCall)
    def get_test_plan(self, test_plan_id: str) -> 'TestPlanUnit':
        """
        Get the test plan with the given identifier.

        :returns:
            The TestPlanUnit object that corresponds to the given identifier.
        :raises KeyError:
            If no such test plan exists
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            The returned object contains parts that may not be covered by the
            public api stability promise. Refer to the documentation of the
            TestPlanUnit class for details.
        """
        UsageExpectation.of(self).enforce()
        return self._context.get_unit(test_plan_id, 'test plan')

    @raises(KeyError, UnexpectedMethodCall)
    def get_category(self, category_id: str) -> 'CategoryUnit':
        """
        Get the category with the given identifier.

        :returns:
            The Category Unit object that corresponds to the given identifier.
        :raises KeyError:
            If no such category exists.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            The returned object contains parts that may not be covered by the
            public api stability promise. Refer to the documentation of the
            CategoryUnit class for details.
        """
        UsageExpectation.of(self).enforce()
        return self._context.get_unit(category_id, 'category')

    @raises(UnexpectedMethodCall)
    def get_participating_categories(self) -> 'List[str]':
        """
        Get a set of category identifiers associated with current test plan.

        :returns:
            A list of category identifiers.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method computes the set of category identifiers that contains each
        category for which at least test might be executed in this session.
        This set does not include boostrap jobs as they must be executed prior
        to actually allowing the user to know what jobs are available.
        """
        UsageExpectation.of(self).enforce()
        test_plan = self._manager.test_plans[0]
        potential_job_list = select_jobs(
            self._context.state.job_list, [test_plan.get_qualifier()])
        return list(set(
            test_plan.get_effective_category_map(potential_job_list).values()))

    @raises(UnexpectedMethodCall)
    def get_static_todo_list(self) -> 'Iterable[str]':
        """
        Get the (static) list of jobs to run.

        :returns:
            A list of identifiers of jobs to run.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be used to obtain the full sequence of jobs that are
        described by the test plan. The result is only influenced by
        :meth:`use_alternate_selection()`. It never grows or shrinks during
        execution of subsequent jobs.

        Please note that returned identifiers may refer to jobs that were
        automatically selected via some mechanism, not necessarily a job
        explicitly requested by the user. Examples of such mechanisms include
        job dependencies, resource dependencies or mandatory jobs.
        """
        UsageExpectation.of(self).enforce()
        return [job.id for job in self._context.state.run_list]

    @raises(UnexpectedMethodCall)
    def get_dynamic_todo_list(self) -> 'List[str]':
        """
        Get the (dynamic) list of jobs to run.

        :returns:
            A list of identifiers of jobs to run.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This methods can be used to obtain the sequence of jobs that are yet to
        be executed. The result is affected by
        :meth:`use_alternate_selection()` as well as :meth:`run_job()`.

        Jobs that cannot be started (due to failed dependencies or unsatisfied
        requirements) are also returned here.  Any attempts to run them via
        :meth:`run_job()` will produce a correct result object with appropriate
        information.

        Please note that returned identifiers may refer to jobs that were
        automatically selected via some mechanism, not necessarily a job
        explicitly requested by the user. Examples of such mechanisms include
        job dependencies, resource dependencies or mandatory jobs.

        .. note::
            It is correct and safe if applications only execute this method
            once and iterate over the result from start to finish, calling
            :meth:`run_job()` and :meth:`use_job_result()`. All dynamics of
            generating jobs is hidden and handled by the :meth:`boostrap()`
            method.
        """
        UsageExpectation.of(self).enforce()
        # XXX: job_state_map is a bit low level, can we avoid that?
        jsm = self._context.state.job_state_map
        return [
            job.id for job in self._context.state.run_list
            if jsm[job.id].result is not jsm[job.id].result.OUTCOME_NONE]

    @raises(ValueError, TypeError, UnexpectedMethodCall)
    def run_job(
        self, job_id: str, ui: 'Union[str, IJobRunnerUI]',
        native: bool
    ) -> 'JobResultBuilder':
        """
        Run a job with the specific identifier.

        :param job_id:
            Identifier of the job to run.
        :param ui:
            The user interface delegate to use. As a special case it can be a
            well-known name of a stock user interface. Currently only the
            'silent' user interface is available.
        :param native:
            Flag indicating that the job will be run natively by the
            application. Normal runner won't be used to execute the job
        :raises KeyError:
            If no such job exists
        :raises ValueError:
            If the well known UI name is not recognized.
        :raises TypeError:
            If the UI is not a IJobRunnerUI subclass.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        :returns:
            JobResultBuilder instance.

        This method can be used to run any job available in the session (not
        only those jobs that are selected, or on the todo list). The result is
        a ResultBuilder object which can be modified if necessary. The result
        builder object can be also converted to a result object and fed back to
        the session via the :meth:`use_job_result()` method.

        It is expected that the caller will follow this protocol for each
        executed job. This API complexity is required to let users interact
        with interactive jobs and let the application do anything it needs to
        to accomplish that.
        """
        UsageExpectation.of(self).enforce()
        if isinstance(ui, IJobRunnerUI):
            pass
        elif isinstance(ui, str):
            if ui == 'silent':
                ui = _SilentUI()
            else:
                raise ValueError("unknown user interface: {!r}".format(ui))
        else:
            raise TypeError("incorrect UI type")
        # XXX: job_state_map is a bit low level, can we avoid that?
        start_time = time.time()
        job_state = self._context.state.job_state_map[job_id]
        job = job_state.job
        ui.considering_job(job, job_state)
        if job_state.can_start():
            ui.about_to_start_running(job, job_state)
            self._context.state.metadata.running_job_name = job.id
            self._manager.checkpoint()
            ui.started_running(job, job_state)
            if not native:
                builder = self._runner.run_job(
                    job, job_state, self._config, ui
                ).get_builder()
            else:
                builder = JobResultBuilder(
                    outcome=IJobResult.OUTCOME_UNDECIDED,
                )
            builder.execution_duration = time.time() - start_time
            self._context.state.metadata.running_job_name = None
            self._manager.checkpoint()
            ui.finished_running(job, job_state, builder.get_result())
        else:
            # Set the outcome of jobs that cannot start to
            # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
            # a job with an OUTCOME_SKIP outcome, if that is the case mirror
            # that outcome. This makes 'skip' stronger than 'not-supported'
            outcome = IJobResult.OUTCOME_NOT_SUPPORTED
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause != InhibitionCause.FAILED_DEP:
                    continue
                related_job_state = self._context.state.job_state_map[
                    inhibitor.related_job.id]
                if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                    outcome = IJobResult.OUTCOME_SKIP
            builder = JobResultBuilder(
                outcome=outcome,
                comments=job_state.get_readiness_description())
            ui.job_cannot_start(job, job_state, builder.get_result())
        ui.finished(job, job_state, builder.get_result())
        # Set up expectations so that run_job() and use_job_result() must be
        # called in pairs and applications cannot just forget and call
        # run_job() all the time.
        allowed_calls = UsageExpectation.of(self).allowed_calls
        del allowed_calls[self.run_job]
        allowed_calls[self.use_job_result] = "remember the result of last job"
        return builder

    @raises(UnexpectedMethodCall)
    def use_job_result(self, job_id: str, result: 'IJobResult') -> None:
        """
        Feed job result back to the session.

        :param job_id:
            Identifier of the job the result is for
        :param result:
            The result object that contains all the information about running
            that job. You can obtain one from a result builder by calling the
            ``builder.get_result()` method.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method is meant to complement :meth:`run_job()`. They are split so
        that the application can freely modify the result object in a single
        _atomic_ operation.

        Note that running a single job and presenting the result back to the
        session may unlock or lock other jobs. For example, running a resource
        job may allow or disallow another job to run (via requirement
        programs). Similar system exists for job dependencies. A job that
        depends on another job will not be able to run if any of its
        dependencies did not complete successfully.
        """
        UsageExpectation.of(self).enforce()
        job = self._context.get_unit(job_id, 'job')
        self._context.state.update_job_result(job, result)
        # Set up expectations so that run_job() and use_job_result() must be
        # called in pairs and applications cannot just forget and call
        # run_job() all the time.
        allowed_calls = UsageExpectation.of(self).allowed_calls
        del allowed_calls[self.use_job_result]
        allowed_calls[self.run_job] = "run another job"

    def get_summary(self) -> 'defaultdict':
        """
        Get a grand total statistic for the jobs that ran.

        :returns:
            A defaultdict mapping the number of jobs that have a given outcome
            to the kind of outcome. E.g. {IJobResult.OUTCOME_PASS: 6, (...)}.
        """
        stats = collections.defaultdict(int)
        for job_state in self._context.state.job_state_map.values():
            if not job_state.result.outcome:
                # job not considered for runnning - let's not pollute summary
                # with data from those jobs
                continue
            stats[job_state.result.outcome] += 1

        return stats

    @raises(UnexpectedMethodCall)
    def finalize_session(self) -> None:
        """
        Finish the execution of the current session.

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        Mark the session as complete, which prohibits running (or rerunning)
        any job.
        """
        UsageExpectation.of(self).enforce()
        if SessionMetaData.FLAG_SUBMITTED not in self._metadata.flags:
            _logger.warning("Finalizing session that hasn't been submitted "
                            "anywhere: %s", self._manager.storage.id)
        self._metadata.flags.remove(SessionMetaData.FLAG_INCOMPLETE)
        self._manager.checkpoint()
        UsageExpectation.of(self).allowed_calls = {
            self.export_to_transport: "to export the results and send them",
            self.export_to_file: "to export the results to a file",
            self.get_resumable_sessions: "to get resume candidates",
            self.start_new_session: "to create a new session",
            self.get_canonical_certification_transport: (
                "create a transport for the C3 system"),
            self.get_canonical_hexr_transport: (
                "create a transport for the HEXR system"),
        }

    @raises(KeyError, TransportError, UnexpectedMethodCall)
    def export_to_transport(
        self, exporter_id: str, transport: ISessionStateTransport
    ) -> dict:
        """
        Export the session using given exporter ID and transport object.

        :param exporter_id:
            The identifier of the exporter unit to use. This must have been
            loaded into the session from an existing provider. Many users will
            want to load the ``2013.com.canonical.palainbox:exporter`` provider
            (via :meth:`load_providers()`.
        :param transport:
            A pre-created transport object such as the `CertificationTransport`
            that is useful for sending data to the Canonical Certification
            Website and HEXR. This can also be any object conforming to the
            appropriate API.
        :returns:
            pass
        :raises KeyError:
            When the exporter unit cannot be found.
        :raises TransportError:
            If the transport fails in any way:
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        UsageExpectation.of(self).enforce()
        exporter = self._manager.create_exporter(exporter_id)
        exported_stream = io.BytesIO()
        exporter.dump_from_session_manager(self._manager, exported_stream)
        exported_stream.seek(0)
        return transport.send(exported_stream)

    @raises(KeyError, OSError)
    def export_to_file(
        self, exporter_id: str, option_list: 'list[str]', dir_path: str
    ) -> str:
        """
        Export the session to file using given exporter ID.

        :param exporter_id:
            The identifier of the exporter unit to use. This must have been
            loaded into the session from an existing provider. Many users will
            want to load the ``2013.com.canonical.palainbox:exporter`` provider
            (via :meth:`load_providers()`.
        :param option_list:
            List of options customary to the exporter that is being created.
        :param dir_path:
            Path to the directory where session file should be written to.
            Note that the file name is automatically generated, based on
            creation time and type of exporter.
        :returns:
            Path to the written file.
        :raises KeyError:
            When the exporter unit cannot be found.
        :raises OSError:
            When there is a problem when writing the output.
        """
        UsageExpectation.of(self).enforce()
        exporter = self._manager.create_exporter(exporter_id, option_list)
        timestamp = datetime.datetime.utcnow().isoformat()
        path = os.path.join(dir_path, ''.join(
            ['submission_', timestamp, '.', exporter.unit.file_extension]))
        with open(path, 'wb') as stream:
            exporter.dump_from_session_manager(self._manager, stream)
        return path

    @raises(ValueError, UnexpectedMethodCall)
    def get_canonical_certification_transport(
        self, secure_id: str, *, staging: bool=False
    ) -> "ISesssionStateTransport":
        """
        Get a transport for the Canonical Certification website.

        :param secure_id:
            The _secure identifier_ of the machine. This is an identifier
            issued by Canonical. It is only applicable to machines that are
            tested by the Hardware Certification team.
        :param staging:
            Flag indicating if the staging server should be used.
        :returns:
            A ISessionStateTransport instance with appropriate configuration.
            In practice the transport object should be passed to
            :meth:`export_to_transport()` and not handled in any other way.
        :raises ValueError:
            if the ``secure_id`` is malformed.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This transport, same as the hexr transport, expects the data created by
        the ``"hexr"`` exporter.
        """
        UsageExpectation.of(self).enforce()
        if staging:
            url = ('https://certification.staging.canonical.com/'
                   'submissions/submit/')
        else:
            url = 'https://certification.canonical.com/submissions/submit/'
        options = "secure_id={}".format(secure_id)
        return CertificationTransport(url, options)

    @raises(UnexpectedMethodCall)
    def get_canonical_hexr_transport(
        self, *, staging: bool=False
    ) -> "ISesssionStateTransport":
        """
        Get a transport for the Canonical HEXR website.

        :param staging:
            Flag indicating if the staging server should be used.
        :returns:
            A ISessionStateTransport instance with appropriate configuration.
            In practice the transport object should be passed to
            :meth:`export_to_transport()` and not handled in any other way.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This transport, same as the certification transport, expects the data
        created by the ``"hexr"`` exporter.
        """
        UsageExpectation.of(self).enforce()
        if staging:
            url = 'https://hexr.staging.canonical.com/checkbox/submit/'
        else:
            url = 'https://hexr.canonical.com/checkbox/submit/'
        options = "submit_to_hexr=1"
        return CertificationTransport(url, options)

    def _get_allowed_calls_in_normal_state(self) -> dict:
        return {
            self.get_job_state: "to access the state of any job",
            self.get_job: "to access the definition of any job",
            self.get_test_plan: "to access the definition of any test plan",
            self.get_category: "to access the definition of ant category",
            self.get_participating_categories: (
                "to access participating categories"),
            self.filter_jobs_by_categories: ("to select the jobs that match"
                "particular category"),
            self.remove_all_filters: "to remove all filters",
            self.get_static_todo_list: "to see what is meant to be executed",
            self.get_dynamic_todo_list: "to see what is yet to be executed",
            self.run_job: "to run a given job",
            self.use_alternate_selection: "to change the selection",
            self.use_job_result: "to feed job result back to the session",
            # XXX: should this be available right off the bat or should we wait
            # until all of the mandatory jobs have been executed.
            self.export_to_transport: "to export the results and send them",
            self.export_to_file: "to export the results to a file",
            self.finalize_session: "to mark the session as complete",
        }


class _SilentUI(IJobRunnerUI):

    def considering_job(self, job, job_state):
        pass

    def about_to_start_running(self, job, job_state):
        pass

    def wait_for_interaction_prompt(self, job):
        pass

    def started_running(self, job, job_state):
        pass

    def about_to_execute_program(self, args, kwargs):
        pass

    def finished_executing_program(self, returncode):
        pass

    def got_program_output(self, stream_name, line):
        pass

    def finished_running(self, job, job_state, job_result):
        pass

    def notify_about_description(self, job):
        pass

    def notify_about_purpose(self, job):
        pass

    def notify_about_steps(self, job):
        pass

    def notify_about_verification(self, job):
        pass

    def job_cannot_start(self, job, job_state, job_result):
        pass

    def finished(self, job, job_state, job_result):
        pass

    def pick_action_cmd(self, action_list, prompt=None):
        pass

    def noreturn_job(self):
        pass
