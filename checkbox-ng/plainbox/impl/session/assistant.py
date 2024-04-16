# This file is part of Checkbox.
#
# Copyright 2012-2023 Canonical Ltd.
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

"""
Session Assistant.

:mod:`plainbox.impl.session.assistant` -- session assistant
===========================================================
"""

import collections
import datetime
import itertools
import json
import logging
import os
import shlex
import time
from tempfile import SpooledTemporaryFile


from checkbox_ng.app_context import application_name

from plainbox.abc import IJobResult
from plainbox.abc import IJobRunnerUI
from plainbox.abc import ISessionStateTransport
from plainbox.i18n import gettext as _
from plainbox.impl.config import Configuration
from plainbox.impl.decorators import raises
from plainbox.impl.developer import UnexpectedMethodCall
from plainbox.impl.developer import UsageExpectation
from plainbox.impl.execution import UnifiedRunner
from plainbox.impl.providers import get_providers
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import JobRunnerUIDelegate
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import select_units
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import JobIdQualifier
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.manager import SessionManager
from plainbox.impl.session.restart import IRestartStrategy
from plainbox.impl.session.restart import detect_restart_strategy
from plainbox.impl.session.restart import RemoteDebRestartStrategy
from plainbox.impl.session.resume import IncompatibleJobError
from plainbox.impl.session.storage import WellKnownDirsHelper
from plainbox.impl.transport import OAuthTransport
from plainbox.impl.transport import TransportError
from plainbox.impl.unit.exporter import ExporterError
from plainbox.impl.unit.unit import Unit
from plainbox.vendor import morris

_logger = logging.getLogger("plainbox.session.assistant")


__all__ = ("SessionAssistant", "SA_RESTARTABLE", "get_all_sa_flags")


# NOTE: There are two tuples related to resume candidates. The internal tuple
# uses the raw SessionStorage object. Since we don't wish to make that a public
# API yet it is not exposed in any of the public side of SessionAssistant APIs.
# The public variant uses the storage identifier (which is just a string) that
# applications are expected to handle as an opaque blob.
InternalResumeCandidate = collections.namedtuple(
    "InternalResumeCandidate", ["storage", "metadata"]
)
ResumeCandidate = collections.namedtuple("ResumeCandidate", ["id", "metadata"])


SA_RESTARTABLE = "restartable"


def get_all_sa_flags():
    return [SA_RESTARTABLE]


def get_known_sa_api_versions():
    return ["0.99"]


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
    """

    # TODO: create a flowchart of possible states

    def __init__(
        self,
        app_id=application_name(),
        app_version=None,
        api_version="0.99",
        api_flags=(),
    ):
        """
        Initialize a new session assistant.

        :param app_id:
            Identifier of the testing application. The identifier should be
            unique and constant throughout the support cycle of the
            application.
        :param app_version:
            Version of the testing application.
        :param api_version:
            Expected API of SessionAssistant. Currently only "0.99" API is
            defined.
        :param api_flags:
            Flags that describe optional API features that this application
            wishes to support. Flags may change the usage expectation of
            session assistant. Currently no flags are supported.
        :raises ValueError:
            When api_version is not recognized.
        :raises ValueError:
            When api_flags contains an unrecognized flag.

        The application identifier is useful to implement session resume
        functionality where the application can easily filter out sessions from
        other programs.
        """
        if api_version not in get_known_sa_api_versions():
            raise ValueError("Unrecognized API version")
        self._flags = set()
        for flag in api_flags:
            if flag == SA_RESTARTABLE:
                self._flags.add(flag)
            else:
                raise ValueError("Unrecognized API flag: {!r}".format(flag))
        self._app_id = app_id
        self._app_version = app_version
        self._api_version = api_version
        self._api_flags = api_flags
        self._config = Configuration()
        Unit.config = self._config
        self._execution_ctrl_list = None  # None is "default"
        self._ctrl_setup_list = []
        # List of providers that were selected. This is buffered until a
        # session is created or resumed.
        self._selected_providers = []
        self.sideloaded_providers = False
        # All the key state for the active session. Technically just the
        # manager matters, the context and metadata are just shortcuts to stuff
        # available on the manager.
        self._exclude_qualifiers = []
        self._manager = None
        self._context = None
        self._metadata = None
        self._runner = None
        self._job_start_time = None
        # Keep a record of jobs run during bootstrap phase
        self._bootstrap_done_list = []
        self._resume_candidates = {}
        self._load_providers()
        UsageExpectation.of(self).allowed_calls = {
            self.start_new_session: "create a new session from scratch",
            self.resume_session: "resume a resume candidate",
            self.get_resumable_sessions: "get resume candidates",
            self.use_alternate_configuration: (
                "use an alternate configuration system"
            ),
            self.use_alternate_execution_controllers: (
                "use an alternate execution controllers"
            ),
            self.get_old_sessions: ("get previously created sessions"),
            self.delete_sessions: ("delete previously created sessions"),
            self.finalize_session: "to finalize session",
            self.configure_application_restart: (
                "configure automatic restart capability"
            ),
            self.use_alternate_restart_strategy: (
                "configure automatic restart capability"
            ),
        }
        # Restart support
        self._restart_cmd_callback = None
        self._restart_strategy = None  # None implies auto-detection

    @property
    def config(self):
        return self._config

    @raises(UnexpectedMethodCall, LookupError)
    def configure_application_restart(
        self, cmd_callback: "Callable[[str], List[str]]"
    ) -> None:
        """
        Configure automatic restart capability.

        :param cmd_callback:
            A callable (function or lambda) that when called with a single
            string argument, session_id, returns a list of strings describing
            how to execute the tool in order to restart a particular session.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        :raises LookupError:
            If no restart strategy was explicitly configured and no strategy
            was found with the auto-detection process.

        .. note:
            This method is only available when the application has initialized
            session assistant with the SA_RESTARTABLE API flag.

        This method configures session assistant for automatic application
        restart. When a job is expected to reboot or shut down the machine but
        the intent is to somehow resume testing automatically after that event,
        test designers can use the 'noreturn' and 'restartable' flags together
        to indicate that the testing process is should be automatically
        resumed when the machine is turned on again.

        The means of re-starting the testing process are unique to each
        operating system environment. Plainbox knows about some restart
        strategies internally. Applications can create additional strategies
        using the :meth:`use_alternate_restart_strategy()` method.
        """
        UsageExpectation.of(self).enforce()
        if self._restart_strategy is None:
            # TODO: REMOTE API RAPI:
            # this heuristic of guessing session type from the title
            # should be changed to a proper arg/flag with the Remote API bump
            try:
                app_blob = json.loads(self._metadata.app_blob.decode("UTF-8"))
                session_type = app_blob["type"]
            except (AttributeError, ValueError, KeyError):
                session_type = "local"
            self._restart_strategy = detect_restart_strategy(
                self, session_type=session_type
            )
        self._restart_cmd_callback = cmd_callback
        # Prevent second call to this method and to the
        # use_alternate_restart_strategy() method.
        allowed_calls = UsageExpectation.of(self).allowed_calls
        del allowed_calls[self.configure_application_restart]
        if self.use_alternate_restart_strategy in allowed_calls:
            del allowed_calls[self.use_alternate_restart_strategy]

    @raises(UnexpectedMethodCall)
    def use_alternate_restart_strategy(
        self, strategy: IRestartStrategy
    ) -> None:
        """
        Setup an alternate restart strategy object.

        :param restart_strategy:
            An object implementing the restart strategy interface. This object
            is used to prepare the system for application restart.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        When this method is called all automatic environment auto-detection is
        disabled and application restart is solely under the control of the
        application.

        The restart interface is very simple, it is comprised of a pair of
        methods, :meth:`IRestartStrategy.prime_application_restart()` and
        :meth:`IRestartStrategy.diffuse_application_restart()`. When the
        application is in a state where it will soon terminate, plainbox will
        call the former of the two methods to _prime_ the system so that
        application will be re-started when the machine is started (or
        rebooted). When the application successfully starts, the _diffuse_
        method will undo what prime did so that the application restart is a
        one-off action.

        The primary use of this method is to let applications support
        environments that are not automatically handled correctly by plainbox.
        """
        UsageExpectation.of(self).enforce()
        self._restart_strategy = strategy
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_restart_strategy
        ]

    @raises(UnexpectedMethodCall)
    def use_alternate_configuration(self, config):
        """
        Use alternate configuration object.

        :param config:
            A Checkbox configuration object.
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
        self._exclude_qualifiers = []
        for pattern in self._config.get_value("test selection", "exclude"):
            self._exclude_qualifiers.append(
                RegExpJobQualifier(pattern, None, False)
            )
        Unit.config = config
        # NOTE: We expect applications to call this at most once.
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_configuration
        ]

    @raises(UnexpectedMethodCall)
    def use_alternate_execution_controllers(
        self,
        ctrl_setup_list: "Iterable[Tuple[IExecutionController, Tuple[Any], Dict[Any]]]",
    ) -> None:
        """
        Use alternate execution controllers.

        :param ctrl_setup_list:
            An iterable with tuples, where each tuple represents a class of
            controller to instantiate, together with *args and **kwargs to
            use when calling its __init__.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method can be used to use any custom execution controllers to
        execute jobs. Normally those should be offered by the
        ``SessionDeviceContext`` (which is a part of the implementation) and
        they should be *good* for any use but as we learned some applications
        needed to offer alternate controllers.

        .. note::
            Please check the source code to understand which values to pass
            here. This method is currently experimental.
        """
        UsageExpectation.of(self).enforce()
        self._ctrl_setup_list = ctrl_setup_list
        # NOTE: We expect applications to call this at most once.
        del UsageExpectation.of(self).allowed_calls[
            self.use_alternate_execution_controllers
        ]

    def _load_providers(self) -> None:
        """Load all Checkbox providers."""
        self._selected_providers = get_providers()
        self.sideloaded_providers = any(
            [p.sideloaded for p in self._selected_providers]
        )

    def get_selected_providers(self):
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
    def get_old_sessions(
        self,
        flags: "Set[str]" = {
            SessionMetaData.FLAG_SUBMITTED,
            SessionMetaData.FLAG_BOOTSTRAPPING,
        },
        allow_not_flagged: bool = True,
    ) -> "List[Tuple[str, Set[str]]]":
        """
        Get the list of previously run sessions.

        :param flags:
            Set of flags from which at least one flag must be present in the
            metadata of the processed session storage in order for that storage
            to be returned.
        :param allow_not_flagged:
            Also return sessions that have no flags attached.
        :returns:
            A list of tuples containing session id and flags that were attached
            to that session.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        UsageExpectation.of(self).enforce()
        for storage in WellKnownDirsHelper.get_storage_list():
            data = storage.load_checkpoint()
            if len(data) == 0:
                continue
            try:
                metadata = SessionPeekHelper().peek(data)
                if metadata.app_id == self._app_id:
                    if (allow_not_flagged and not metadata.flags) or (
                        metadata.flags & flags
                    ):
                        yield storage.id, metadata.flags
            except SessionResumeError as exc:
                _logger.info(
                    "Exception raised when trying to peek session" "data: %s",
                    str(exc),
                )

    def delete_sessions(self, session_ids: "List[str]") -> None:
        """
        Delete session storages.

        :param session_ids:
            A list of session ids which storages should be removed.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        .. note::
            If the session is not found in the currently selected session
            repository, it is silently ignored.
        """
        for storage in WellKnownDirsHelper.get_storage_list():
            if storage.id in session_ids:
                storage.remove()

    @raises(UnexpectedMethodCall)
    def start_new_session(
        self, title: str, runner_cls=UnifiedRunner, runner_kwargs=dict()
    ):
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
        self._manager = SessionManager.create(prefix=title + "-")
        self._context = self._manager.add_local_device_context()
        for provider in self._selected_providers:
            if provider.problem_list:
                _logger.error(
                    "Problems encountered when loading %s provider: %s",
                    provider.name,
                    provider.problem_list,
                )
            self._context.add_provider(provider)
        self._metadata = self._context.state.metadata
        self._metadata.app_id = self._app_id
        self._metadata.title = title
        self._metadata.flags = {SessionMetaData.FLAG_BOOTSTRAPPING}
        self._manager.checkpoint()
        self._command_io_delegate = JobRunnerUIDelegate(_SilentUI())
        self._init_runner(runner_cls, runner_kwargs)
        self.session_available(self._manager.storage.id)
        _logger.info("New session created: %s", title)
        UsageExpectation.of(self).allowed_calls = {
            self.get_test_plans: "to get the list of available test plans",
            self.get_test_plan: "to get particular test plan object",
            self.select_test_plan: "select the test plan to execute",
            self.get_session_id: "to get the id of currently running session",
            self.hand_pick_jobs: "select jobs to run (w/o a test plan)",
            self.get_resumable_sessions: "get resume candidates",
            self.finalize_session: "to finalize session",
            self.configure_application_restart: (
                "configure automatic restart capability"
            ),
            self.use_alternate_restart_strategy: (
                "configure automatic restart capability"
            ),
        }

    @raises(KeyError, UnexpectedMethodCall, IncompatibleJobError)
    def resume_session(
        self, session_id: str, runner_cls=UnifiedRunner, runner_kwargs=dict()
    ) -> "SessionMetaData":
        """
        Resume a session.

        :param session_id:
            The identifier of the session to resume.
        :returns:
            Resumed session metadata.
        :raises KeyError:
            If the session with a given session_id cannot be found.
        :raises IncompatibleJobError:
            If the session is incompatible due to a job changing
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
        all_units = list(
            itertools.chain(*[p.unit_list for p in self._selected_providers])
        )
        if session_id not in self._resume_candidates:
            for resume_candidate in self.get_resumable_sessions():
                if resume_candidate.id == session_id:
                    break
            else:
                raise KeyError("Unknown session {}".format(session_id))

        self._manager = SessionManager.load_session(
            all_units, self._resume_candidates[session_id][0]
        )
        self._context = self._manager.default_device_context
        self._metadata = self._context.state.metadata
        self._command_io_delegate = JobRunnerUIDelegate(_SilentUI())
        self._init_runner(runner_cls, runner_kwargs)
        if self._metadata.running_job_name:
            job = self._context.get_unit(
                self._metadata.running_job_name, "job"
            )
            if "autorestart" in job.get_flag_set():
                result = JobResultBuilder(
                    outcome=(
                        IJobResult.OUTCOME_PASS
                        if "noreturn" in job.get_flag_set()
                        else IJobResult.OUTCOME_FAIL
                    ),
                    return_code=0,
                    io_log_filename=self._runner.get_record_path_for_job(job),
                ).get_result()
                self._context.state.update_job_result(job, result)
                self._manager.checkpoint()
        self._restart_strategy = detect_restart_strategy(self)
        _logger.info("Session strategy: %r", self._restart_strategy)
        self._job_start_time = self._metadata.last_job_start_time
        if self._restart_strategy is not None:
            self._restart_strategy.diffuse_application_restart(self._app_id)
        self.session_available(self._manager.storage.id)
        _logger.info("Session resumed: %s", session_id)
        if SessionMetaData.FLAG_TESTPLANLESS in self._metadata.flags:
            UsageExpectation.of(self).allowed_calls = (
                self._get_allowed_calls_in_normal_state()
            )
        else:
            UsageExpectation.of(self).allowed_calls = {
                self.get_resumable_sessions: "to get resume candidates",
                self.select_test_plan: "to save test plan selection",
                self.use_alternate_configuration: (
                    "use an alternate configuration system"
                ),
            }
        return self._metadata

    @raises(UnexpectedMethodCall)
    def get_resumable_sessions(self) -> "Tuple[str, SessionMetaData]":
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
        # also, when this function is called invalidate the cache, as it may
        # have been modified by some external source
        self._resume_candidates = {}
        for storage in WellKnownDirsHelper.get_storage_list():
            data = storage.load_checkpoint()
            if len(data) == 0:
                continue
            try:
                metadata = SessionPeekHelper().peek(data)
            except SessionResumeError:
                _logger.info(
                    "Exception raised when trying to resume " "session: %s",
                    str(storage.id),
                )
            else:
                if (
                    metadata.app_id == self._app_id
                    and SessionMetaData.FLAG_INCOMPLETE in metadata.flags
                ):
                    self._resume_candidates[storage.id] = (
                        InternalResumeCandidate(storage, metadata)
                    )
                    UsageExpectation.of(self).allowed_calls[
                        self.resume_session
                    ] = "resume session"
                    yield ResumeCandidate(storage.id, metadata)

    def update_app_blob(self, app_blob: bytes) -> None:
        """
        Update custom app data and save the session in the session storage.

        :param app_blob:
            Bytes sequence containing JSON-ised app_blob object.

        """
        if self._context.state.metadata.app_blob == b"":
            updated_blob = app_blob
        else:
            current_dict = json.loads(
                self._context.state.metadata.app_blob.decode("UTF-8")
            )
            current_dict.update(json.loads(app_blob.decode("UTF-8")))
            updated_blob = json.dumps(current_dict).encode("UTF-8")
        self._context.state.metadata.app_blob = updated_blob
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
    def get_test_plans(self) -> "List[str]":
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
        return [
            unit.id
            for unit in self._context.unit_list
            if unit.Meta.name == "test plan"
        ]

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
        test_plan = self._context.get_unit(test_plan_id, "test plan")
        self._manager.test_plans = (test_plan,)
        self._manager.checkpoint()
        UsageExpectation.of(self).allowed_calls = {
            self.bootstrap: "to run the bootstrap process",
            self.get_bootstrap_todo_list: "to get bootstrapping jobs",
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
        in the template. This mechanism is subject to the validation system
        (invalid units are discarded).

        When this method returns (which can take a while) the session is now
        ready for running any jobs.

        .. warning:
            This method will not return until the bootstrap process is
            finished. This can take any amount of time (easily over one minute)
        """
        UsageExpectation.of(self).enforce()
        # NOTE: there is next-to-none UI here as bootstrap jobs are limited to
        # just resource jobs (including their dependencies) so there should be
        # very little UI required.
        desired_job_list = select_units(
            self._context.state.job_list,
            [
                plan.get_bootstrap_qualifier()
                for plan in (self._manager.test_plans)
            ]
            + self._exclude_qualifiers,
        )
        self._context.state.update_desired_job_list(
            desired_job_list, include_mandatory=False
        )
        for job in self._context.state.run_list:
            if self._context.state.job_state_map[job.id].result_history:
                continue
            UsageExpectation.of(self).allowed_calls[
                self.run_job
            ] = "to run bootstrapping job"
            rb = self.run_job(job.id, "silent", False)
            self.use_job_result(job.id, rb.get_result())
        # Perform initial selection -- we want to run everything that is
        # described by the test plan that was selected earlier.
        desired_job_list = select_units(
            self._context.state.job_list,
            [plan.get_qualifier() for plan in self._manager.test_plans]
            + self._exclude_qualifiers,
        )
        self._context.state.update_desired_job_list(desired_job_list)
        # Set subsequent usage expectations i.e. all of the runtime parts are
        # available now.
        UsageExpectation.of(self).allowed_calls = (
            self._get_allowed_calls_in_normal_state()
        )
        self._metadata.flags = {SessionMetaData.FLAG_INCOMPLETE}
        self._manager.checkpoint()

    @raises(UnexpectedMethodCall)
    def hand_pick_jobs(self, id_patterns: "Iterable[str]"):
        """
        Select jobs to run. Don't use test plans.

        :param id_patterns:
            List of regex patterns that jobs' id must match in order to be
            selected.

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        Use this method if you want to run particular jobs from all of the
        loaded providers. They don't have to be included in any test plan.
        There is no bootstrapping done, so templates are not intantiated, thus
        selection is done only among explicit jobs.
        """
        UsageExpectation.of(self).enforce()
        qualifiers = []
        for pattern in id_patterns:
            qualifiers.append(
                FieldQualifier(
                    "id",
                    PatternMatcher("^{}$".format(pattern)),
                    Origin("hand-pick"),
                )
            )
        jobs = select_units(self._context.state.job_list, qualifiers)
        self._context.state.update_desired_job_list(jobs)
        self._metadata.flags = {
            SessionMetaData.FLAG_INCOMPLETE,
            SessionMetaData.FLAG_TESTPLANLESS,
        }
        UsageExpectation.of(self).allowed_calls = (
            self._get_allowed_calls_in_normal_state()
        )

    @raises(UnexpectedMethodCall)
    def get_bootstrap_todo_list(self):
        """
        Get a list of ids that should be run in while bootstrapping)

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        This method, together with :meth:`run_job`, can be used instead of
        :meth:`boostrap` to have control over when bootstrapping jobs are run.
        E.g. to inform the user about the progress
        """
        UsageExpectation.of(self).enforce()
        desired_job_list = select_units(
            self._context.state.job_list,
            [
                plan.get_bootstrap_qualifier()
                for plan in (self._manager.test_plans)
            ]
            + self._exclude_qualifiers,
        )
        self._context.state.update_desired_job_list(
            desired_job_list, include_mandatory=False
        )
        UsageExpectation.of(self).allowed_calls.update(
            self._get_allowed_calls_in_normal_state()
        )
        return [job.id for job in self._context.state.run_list]

    @raises(UnexpectedMethodCall)
    def finish_bootstrap(self):
        """
        Prepare the final list of jobs to be run

        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.

        If the application controls individual bootstrapping jobs' execution
        then it should call this method after all bootstrapping is done.
        XXX: this could be automated by adding some state information to
        SessionAssistant class, but if the app wants fine control, ilet's let
        it have it.
        """
        UsageExpectation.of(self).enforce()
        # Perform initial selection -- we want to run everything that is
        # described by the test plan that was selected earlier.
        desired_job_list = select_units(
            self._context.state.job_list,
            [plan.get_qualifier() for plan in self._manager.test_plans]
            + self._exclude_qualifiers
            + [
                JobIdQualifier(
                    "com.canonical.plainbox::collect-manifest", None, False
                )
            ],
        )
        self._context.state.update_desired_job_list(desired_job_list)
        # Set subsequent usage expectations i.e. all of the runtime parts are
        # available now.
        UsageExpectation.of(self).allowed_calls = (
            self._get_allowed_calls_in_normal_state()
        )
        self._metadata.flags = {SessionMetaData.FLAG_INCOMPLETE}
        self._manager.checkpoint()
        # No bootstrap is done update the cache of jobs that were run
        # during bootstrap phase
        self._bootstrap_done_list = self.get_dynamic_done_list()

    @raises(KeyError, UnexpectedMethodCall)
    def use_alternate_selection(self, selection: "Iterable[str]"):
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
        self._metadata.custom_joblist = True
        desired_job_list = []
        rejected_job_list = []
        for job_id in self.get_static_todo_list():
            if job_id in selection:
                desired_job_list.append(self._context.get_unit(job_id, "job"))
            else:
                rejected_job_list.append(job_id)
        self._metadata.rejected_jobs = rejected_job_list
        self._context.state.update_desired_job_list(desired_job_list)

    @raises(UnexpectedMethodCall)
    def filter_jobs_by_categories(self, categories: "Iterable[str]"):
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
        selection = [
            job.id
            for job in [
                self.get_job(job_id) for job_id in self.get_static_todo_list()
            ]
            if job.category_id in categories
        ]
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
        desired_job_list = select_units(
            self._context.state.job_list,
            [plan.get_qualifier() for plan in self._manager.test_plans],
        )
        self._context.state.update_desired_job_list(desired_job_list)

    @raises(KeyError, UnexpectedMethodCall)
    def get_job_state(self, job_id: str) -> "JobState":
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
        return self._context.get_unit(job_id, "job")

    @raises(KeyError, UnexpectedMethodCall)
    def get_test_plan(self, test_plan_id: str) -> "TestPlanUnit":
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
        return self._context.get_unit(test_plan_id, "test plan")

    @raises(KeyError, UnexpectedMethodCall)
    def get_category(self, category_id: str) -> "CategoryUnit":
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
        return self._context.get_unit(category_id, "category")

    @raises(UnexpectedMethodCall)
    def get_participating_categories(self) -> "List[str]":
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
        return list(
            set(
                test_plan.get_effective_category_map(
                    self._context.state.run_list
                ).values()
            )
        )

    @raises(UnexpectedMethodCall)
    def get_mandatory_jobs(self) -> "Iterable[str]":
        """
        Get the list of ids of mandatory jobs.

        :returns:
            A list of identifiers of mandatory jobs scheduled to run.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        UsageExpectation.of(self).enforce()
        test_plan = self._manager.test_plans[0]
        return [
            job.id
            for job in select_units(
                self._context.state.job_list,
                [test_plan.get_mandatory_qualifier()],
            )
        ]

    @raises(UnexpectedMethodCall)
    def get_static_todo_list(self) -> "Iterable[str]":
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
    def get_dynamic_done_list(self) -> "List[str]":
        """
        Get the (dynamic) list of jobs with an outcome.

        :returns:
            A list of indentifiers of jobs that have run.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        jsm = self._context.state.job_state_map
        return [
            job_id
            for job_id, state in jsm.items()
            if (
                state.result.outcome is not None
                and job_id not in self._bootstrap_done_list
            )
        ]

    @raises(UnexpectedMethodCall)
    def get_dynamic_todo_list(self) -> "List[str]":
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
            job.id
            for job in self._context.state.run_list
            if jsm[job.id].result.outcome is None
        ]

    def _strtobool(self, val):
        return val.lower() in ("y", "yes", "t", "true", "on", "1")

    @raises(SystemExit, UnexpectedMethodCall)
    def get_manifest_repr(self) -> "Dict[List[Dict]]":
        """
        Get the manifest units required by the jobs selection.

        :returns:
            A dict of manifest questions.
        :raises SystemExit:
            When the launcher manifest section contains invalid entries.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        UsageExpectation.of(self).enforce()
        # XXX: job_state_map is a bit low level, can we avoid that?
        jsm = self._context.state.job_state_map
        todo_list = [
            job
            for job in self._context.state.run_list
            if jsm[job.id].result.outcome is None
        ]
        expression_list = []
        manifest_id_set = set()
        for job in todo_list:
            if job.get_resource_program():
                expression_list.extend(
                    job.get_resource_program().expression_list
                )
        for e in expression_list:
            manifest_id_set.update(e.manifest_id_list)
        manifest_list = [
            unit
            for unit in self._context.unit_list
            if unit.Meta.name == "manifest entry"
            and unit.id in manifest_id_set
        ]
        manifest_cache = {}
        manifest = WellKnownDirsHelper.manifest_file()
        if os.path.isfile(manifest):
            with open(manifest, "rt", encoding="UTF-8") as stream:
                manifest_cache = json.load(stream)
        if self._config is not None and self._config.manifest:
            for manifest_id in self._config.manifest:
                manifest_cache.update(
                    {manifest_id: self._config.manifest[manifest_id]}
                )
        manifest_info_dict = dict()
        for m in manifest_list:
            prompt = m.prompt()
            if prompt is None:
                if m.value_type == "bool":
                    prompt = "Does this machine have this piece of hardware?"
                elif m.value_type == "natural":
                    prompt = "Please enter the requested data:"
                else:
                    _logger.error("Unsupported value-type: '%s'", m.value_type)
                    continue
            if prompt not in manifest_info_dict:
                manifest_info_dict[prompt] = []
            manifest_info = {
                "id": m.id,
                "partial_id": m.partial_id,
                "name": m.name,
                "value_type": m.value_type,
            }
            try:
                value = manifest_cache[m.id]
                if m.value_type == "bool":
                    if isinstance(manifest_cache[m.id], str):
                        value = self._strtobool(manifest_cache[m.id])
                elif m.value_type == "natural":
                    value = int(manifest_cache[m.id])
            except ValueError:
                _logger.error(
                    ("Invalid manifest %s value '%s'"),
                    m.id,
                    manifest_cache[m.id],
                )
                raise SystemExit(1)
            except KeyError:
                value = None
            manifest_info.update({"value": value})
            manifest_info_dict[prompt].append(manifest_info)
        return manifest_info_dict

    def save_manifest(self, manifest_answers):
        """
        Record the manifest on disk.
        """
        manifest_cache = dict()
        manifest = WellKnownDirsHelper.manifest_file()
        if os.path.isfile(manifest):
            with open(manifest, "rt", encoding="UTF-8") as stream:
                manifest_cache = json.load(stream)
        manifest_cache.update(manifest_answers)
        print("Saving manifest to {}".format(manifest))
        with open(manifest, "wt", encoding="UTF-8") as stream:
            json.dump(manifest_cache, stream, sort_keys=True, indent=2)

    def note_metadata_starting_job(self, job, job_state):
        """
        Update the session metadata to make a resumable checkpoint.

        Without the information that this function stores, a session will not
        be resumable. This also creates a checkpoint so that the information is
        both in the session and on disk.
        """
        self._metadata.running_job_name = job["id"]
        self._metadata.last_job_start_time = time.time()
        self._manager.checkpoint()

    @raises(ValueError, TypeError, UnexpectedMethodCall)
    def run_job(
        self, job_id: str, ui: "Union[str, IJobRunnerUI]", native: bool
    ) -> "JobResultBuilder":
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
            if ui == "silent":
                ui = _SilentUI()
            elif ui == "piano":
                ui = _PianoUI()
            else:
                raise ValueError("unknown user interface: {!r}".format(ui))
        else:
            raise TypeError("incorrect UI type")
        warm_up_list = self._runner.get_warm_up_sequence(
            self._context.state.run_list
        )
        if warm_up_list:
            for warm_up_func in warm_up_list:
                warm_up_func()
        # XXX: job_state_map is a bit low level, can we avoid that?
        self._job_start_time = time.time()
        self._metadata.last_job_start_time = self._job_start_time
        job_state = self._context.state.job_state_map[job_id]
        job = job_state.job
        ui.considering_job(job, job_state)
        if job_state.can_start():
            ui.about_to_start_running(job, job_state)
            self._context.state.metadata.running_job_name = job.id
            self._manager.checkpoint()
            autorestart = (
                self._restart_strategy is not None
                and "autorestart" in job.get_flag_set()
            )
            if autorestart:
                restart_cmd = ""
                if self._restart_cmd_callback:
                    restart_cmd = " ".join(
                        shlex.quote(cmd_part)
                        for cmd_part in self._restart_cmd_callback(
                            self._manager.storage.id
                        )
                    )
                self._restart_strategy.prime_application_restart(
                    self._app_id, self._manager.storage.id, restart_cmd
                )
            elif (
                isinstance(self._restart_strategy, RemoteDebRestartStrategy)
                and "noreturn" in job.get_flag_set()
            ):
                self._restart_strategy.prime_application_restart(
                    self._app_id,
                    self._manager.storage.id,
                    RemoteDebRestartStrategy.service_name,
                )
            ui.started_running(job, job_state)
            if "noreturn" in job.get_flag_set():
                # 'share' the information how to respawn the application
                # once all the test actions are performed.
                # tests can read this from $PLAINBOX_PROVIDER_SHARE envvar
                session_share = WellKnownDirsHelper.session_share(
                    self.get_session_id()
                )
                respawn_cmd_file = os.path.join(
                    session_share, "__respawn_checkbox"
                )
                if self._restart_cmd_callback:
                    with open(respawn_cmd_file, "wt") as f:
                        if isinstance(
                            self._restart_strategy, RemoteDebRestartStrategy
                        ):
                            service = RemoteDebRestartStrategy.service_name
                            f.writelines(
                                [
                                    "sudo systemctl enable {}\n".format(
                                        service
                                    ),
                                    "sudo systemctl start {}".format(service),
                                ]
                            )
                        else:
                            f.writelines(
                                self._restart_cmd_callback(
                                    self.get_session_id()
                                )
                            )
            if not native:
                result = self._runner.run_job(
                    job, job_state, self._config.environment, ui
                )
                builder = result.get_builder()
            else:
                builder = JobResultBuilder(
                    outcome=IJobResult.OUTCOME_UNDECIDED,
                )
            if autorestart:
                self._restart_strategy.diffuse_application_restart(
                    self._app_id
                )
            self._manager.checkpoint()
            ui.finished_running(job, job_state, builder.get_result())
        else:
            # Set the outcome of jobs that cannot start to
            # OUTCOME_NOT_SUPPORTED _except_ if any of the inhibitors point to
            # a job with an OUTCOME_SKIP outcome, if that is the case mirror
            # that outcome. This makes 'skip' stronger than 'not-supported'
            outcome = IJobResult.OUTCOME_NOT_SUPPORTED
            for inhibitor in job_state.readiness_inhibitor_list:
                if (
                    inhibitor.cause == InhibitionCause.FAILED_RESOURCE
                    and "fail-on-resource" in job.get_flag_set()
                ):
                    outcome = IJobResult.OUTCOME_FAIL
                    break
                elif inhibitor.cause != InhibitionCause.FAILED_DEP:
                    continue
                related_job_state = self._context.state.job_state_map[
                    inhibitor.related_job.id
                ]
                if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                    outcome = IJobResult.OUTCOME_SKIP
            builder = JobResultBuilder(
                outcome=outcome, comments=job_state.get_readiness_description()
            )
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
    def use_job_result(
        self, job_id: str, result: "IJobResult", override_last: bool = False
    ) -> None:
        """
        Feed job result back to the session.

        :param job_id:
            Identifier of the job the result is for
        :param result:
            The result object that contains all the information about running
            that job. You can obtain one from a result builder by calling the
            `builder.get_result()` method.
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
        job = self._context.get_unit(job_id, "job")
        job_state = self._context.state.job_state_map[job_id]
        if len(job_state.result_history) > 0 and override_last:
            job_state.result_history = job_state.result_history[:-1]
        if self._job_start_time:
            result.execution_duration = time.time() - self._job_start_time
        self._context.state.update_job_result(job, result)
        try:
            if self._config.get_value("ui", "auto_retry"):
                self._context.state.job_state_map[job_id].attempts -= 1
        except AttributeError:
            # auto_retry is not available in a bare PlainboxConfig (which
            # happens when using `checkbox-cli run, or plainbox`, and with old,
            # legacy Launchers. They are not expected to do auto-retries.
            pass
        self._manager.checkpoint()
        # Set up expectations so that run_job() and use_job_result() must be
        # called in pairs and applications cannot just forget and call
        # run_job() all the time.
        allowed_calls = UsageExpectation.of(self).allowed_calls
        del allowed_calls[self.use_job_result]
        allowed_calls[self.run_job] = "run another job"

    @raises(UnexpectedMethodCall)
    def get_rerun_candidates(self, session_type="manual"):
        """
        Get all the tests that might be selected for rerunning.

        :returns:
            The JobUnits that failed previously and satisfy the predicate.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        rerun_candidates = []
        todo_list = self.get_static_todo_list()
        job_states = {
            job_id: self.get_job_state(job_id) for job_id in todo_list
        }
        for job_id, job_state in job_states.items():
            if session_type == "manual":
                if job_state.result.outcome in (
                    IJobResult.OUTCOME_FAIL,
                    IJobResult.OUTCOME_CRASH,
                    IJobResult.OUTCOME_SKIP,
                    IJobResult.OUTCOME_NOT_SUPPORTED,
                ):
                    rerun_candidates.append(self.get_job(job_id))
            if session_type == "auto":
                if job_state.result.outcome is None:
                    rerun_candidates.append(self.get_job(job_id))
                    continue
                if job_state.attempts == 0:
                    continue
                if job_state.effective_auto_retry == "no":
                    continue
                if job_state.result.outcome in (
                    IJobResult.OUTCOME_NOT_SUPPORTED
                ):
                    for inhibitor in job_state.readiness_inhibitor_list:
                        if inhibitor.cause == InhibitionCause.FAILED_DEP:
                            rerun_candidates.append(self.get_job(job_id))
                if job_state.result.outcome in (
                    IJobResult.OUTCOME_FAIL,
                    IJobResult.OUTCOME_CRASH,
                ):
                    rerun_candidates.append(self.get_job(job_id))
        return rerun_candidates

    @raises(UnexpectedMethodCall)
    def prepare_rerun_candidates(self, rerun_candidates):
        """
        Rearm jobs so they can be run again.

        :returns:
            List of JobUnits armed for running.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        candidates = []
        resources_to_rerun = []
        for job in rerun_candidates:
            job_state = self.get_job_state(job.id)
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause == InhibitionCause.FAILED_DEP:
                    resources_to_rerun.append(inhibitor.related_job)
        # make the candidates pop only once in the list
        final_candidates = []
        for job in resources_to_rerun + list(rerun_candidates):
            if job not in final_candidates:
                final_candidates.append(job)
        # reset outcome of jobs that are selected for re-running
        for job in final_candidates:
            self.get_job_state(job.id).result = MemoryJobResult({})
            candidates.append(job.id)
            _logger.info(
                "{}: {} attempts".format(
                    job.id, self.get_job_state(job.id).attempts
                )
            )
        return candidates

    def get_summary(self) -> "defaultdict":
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
        any job. finalize_session will be ignored if session has already been
        finalized; this frees applications from keeping state information in
        them.
        """
        UsageExpectation.of(self).enforce()
        finalizable_flags = [
            SessionMetaData.FLAG_INCOMPLETE,
            SessionMetaData.FLAG_BOOTSTRAPPING,
        ]

        if all(flag not in self._metadata.flags for flag in finalizable_flags):
            _logger.info(
                "finalize_session called for already finalized session: %s",
                self._manager.storage.id,
            )
            # leave the same usage expectations
            return
        ignored_flags = {
            SessionMetaData.FLAG_SUBMITTED,
            SessionMetaData.FLAG_BOOTSTRAPPING,
        }
        if not (ignored_flags & set(self._metadata.flags)):
            _logger.warning(
                "Finalizing session that hasn't been submitted "
                "anywhere: %s",
                self._manager.storage.id,
            )
        for flag in finalizable_flags:
            if flag in self._metadata.flags:
                self._metadata.flags.remove(flag)
        self._manager.checkpoint()
        UsageExpectation.of(self).allowed_calls = {
            self.finalize_session: "to finalize session",
            self.export_to_transport: "to export the results and send them",
            self.export_to_file: "to export the results to a file",
            self.export_to_stream: "to export the results to a stream",
            self.get_resumable_sessions: "to get resume candidates",
            self.start_new_session: "to create a new session",
            self.resume_session: "to resume a session",
            self.get_old_sessions: ("get previously created sessions"),
            self.delete_sessions: ("delete previously created sessions"),
        }

    @raises(KeyError, TransportError, UnexpectedMethodCall, ExporterError)
    def export_to_transport(
        self,
        exporter_id: str,
        transport: ISessionStateTransport,
        options: "Sequence[str]" = (),
    ) -> dict:
        """
        Export the session using given exporter ID and transport object.

        :param exporter_id:
            The identifier of the exporter unit to use. This must have been
            loaded into the session from an existing provider. Many users will
            want to load the ``com.canonical.palainbox:exporter`` provider
        :param transport:
            A pre-created transport object such as the `CertificationTransport`
            that is useful for sending data to the Canonical Certification
            Website. This can also be any object conforming to the
            appropriate API.
        :param options:
            (optional) List of options customary to the exporter that is being
            created.
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
        :raises ExporterError:
            If the exporter unit reported an error.
        """
        UsageExpectation.of(self).enforce()
        try:
            exporter = self._manager.create_exporter(exporter_id, options)
            exported_stream = SpooledTemporaryFile(max_size=102400, mode="w+b")
            exporter.dump_from_session_manager(self._manager, exported_stream)
            exported_stream.seek(0)
        except ExporterError as exc:
            logging.warning(
                _("Transport skipped due to exporter error (%s)"),
                transport.url,
            )
            raise
        result = transport.send(exported_stream)
        if SessionMetaData.FLAG_SUBMITTED not in self._metadata.flags:
            self._metadata.flags.add(SessionMetaData.FLAG_SUBMITTED)
            self._manager.checkpoint()
        return result

    @raises(KeyError, OSError)
    def export_to_file(
        self,
        exporter_id: str,
        option_list: "list[str]",
        dir_path: str,
        filename: str = None,
    ) -> str:
        """
        Export the session to file using given exporter ID.

        :param exporter_id:
            The identifier of the exporter unit to use. This must have been
            loaded into the session from an existing provider. Many users will
            want to load the ``com.canonical.palainbox:exporter`` provider
        :param option_list:
            List of options customary to the exporter that is being created.
        :param dir_path:
            Path to the directory where session file should be written to.
            Note that the file name is automatically generated, based on
        :param filename:
            Optional file name (without extension)
            By default, the file name is automatically generated, based on
            creation time and type of exporter.
        :returns:
            Path to the written file.
        :raises KeyError:
            When the exporter unit cannot be found.
        :raises OSError:
            When there is a problem when writing the output.
        """
        UsageExpectation.of(self).enforce()
        exporter = self._manager.create_exporter(
            exporter_id, option_list, strict=False
        )

        # LP:1585326 maintain isoformat but removing ':' chars that cause
        # issues when copying files.
        isoformat = "%Y-%m-%dT%H.%M.%S.%f"
        timestamp = datetime.datetime.utcnow().strftime(isoformat)
        basename = "submission_" + timestamp
        if filename:
            basename = filename
        path = os.path.join(
            dir_path, "".join([basename, ".", exporter.unit.file_extension])
        )
        with open(path, "wb") as stream:
            exporter.dump_from_session_manager(self._manager, stream)
        return path

    @raises(KeyError, OSError)
    def export_to_stream(
        self, exporter_id: str, option_list: "list[str]", stream
    ) -> None:
        """
        Export the session to file using given exporter ID.

        :param exporter_id:
            The identifier of the exporter unit to use. This must have been
            loaded into the session from an existing provider. Many users will
            want to load the ``com.canonical.palainbox:exporter`` provider
        :param option_list:
            List of options customary to the exporter that is being created.
        :param stream:
            Stream to write the report to.
        :returns:
            Path to the written file.
        :raises KeyError:
            When the exporter unit cannot be found.
        :raises OSError:
            When there is a problem when writing the output.
        """
        UsageExpectation.of(self).enforce()
        exporter = self._manager.create_exporter(exporter_id, option_list)
        exporter.dump_from_session_manager(self._manager, stream)
        if SessionMetaData.FLAG_SUBMITTED not in self._metadata.flags:
            self._metadata.flags.add(SessionMetaData.FLAG_SUBMITTED)
            self._manager.checkpoint()

    @raises(UnexpectedMethodCall, KeyError)
    def get_ubuntu_sso_oauth_transport(
        self, transport_details: dict
    ) -> "ISessionStateTransport":
        """
        Get a transport for OAuth.

        :param transport_details:
            Dictionary containing necessray transport configuration.
        :raises KeyError:
            When transport_details is missing vital information.
        :raises UnexpectedMethodCall:
            If the call is made at an unexpected time. Do not catch this error.
            It is a bug in your program. The error message will indicate what
            is the likely cause.
        """
        UsageExpectation.of(self).enforce()
        url = transport_details["url"]
        return OAuthTransport(url, "", transport_details)

    def send_signal(self, signal, target_user):
        self._runner.send_signal(signal, target_user)

    def _get_allowed_calls_in_normal_state(self) -> dict:
        return {
            self.get_job_state: "to access the state of any job",
            self.get_rerun_candidates: "to get list of rerunnable jobs",
            self.get_job: "to access the definition of any job",
            self.get_test_plan: "to access the definition of any test plan",
            self.get_category: "to access the definition of ant category",
            self.get_participating_categories: (
                "to access participating categories"
            ),
            self.get_mandatory_jobs: "to get all mandatory job ids",
            self.filter_jobs_by_categories: (
                "to select the jobs that match particular category"
            ),
            self.remove_all_filters: "to remove all filters",
            self.get_static_todo_list: "to see what is meant to be executed",
            self.get_dynamic_todo_list: "to see what is yet to be executed",
            self.get_manifest_repr: ("to get participating manifest units"),
            self.run_job: "to run a given job",
            self.use_alternate_selection: "to change the selection",
            self.get_resumable_sessions: "get resume candidates",
            self.hand_pick_jobs: "to generate new selection and use it",
            self.use_job_result: "to feed job result back to the session",
            # XXX: should this be available right off the bat or should we wait
            # until all of the mandatory jobs have been executed.
            self.export_to_transport: "to export the results and send them",
            self.export_to_file: "to export the results to a file",
            self.export_to_stream: "to export the results to a stream",
            self.finalize_session: "to mark the session as complete",
            self.get_session_id: "to get the id of currently running session",
            self.finish_bootstrap: "to finish bootstrapping",
        }

    def _init_runner(self, runner_cls, runner_kwargs=dict()):
        self._execution_ctrl_list = []
        for ctrl_cls, args, kwargs in self._ctrl_setup_list:
            self._execution_ctrl_list.append(
                ctrl_cls(self._context.provider_list, *args, **kwargs)
            )
        runner_kwargs["jobs_io_log_dir"] = WellKnownDirsHelper.io_logs(
            self._manager.storage.id
        )
        runner_kwargs["command_io_delegate"] = self._command_io_delegate
        runner_kwargs["execution_ctrl_list"] = (
            self._execution_ctrl_list or None
        )

        self._runner = runner_cls(
            self._manager.storage.id,
            self._context.provider_list,
            **runner_kwargs
        )
        return


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


class _PianoUI(_SilentUI):
    """A near silent UI that just prints the outcome when a job fails"""

    def finished(self, job, job_state, job_result):
        if job_result.outcome == IJobResult.OUTCOME_FAIL:
            print(_("Outcome: job failed"))
