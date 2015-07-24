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

"""Session Assistant."""

import io
import os

from plainbox.abc import IJobRunnerUI
from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.applogic import run_job_if_possible
from plainbox.impl.runner import JobRunner
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionManager
from plainbox.public import get_providers


class SessionAssistant:

    """
    Assisting class to simplify common testing scenarios.

    The assistant acts as a middle-man between the session manager and the
    application. It handles all currently known stages of the testing
    work-flow.
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
        self._config = PlainBoxConfig().get()
        # start_new_session()
        self._manager = None
        self._context = None
        self._metadata = None
        # add_providers()
        self._provider_list = None

    def start_new_session(self, title):
        """
        Create a new testing session.

        :param title:
            Title of the session.

        This method must be used to create a new session. This will create some
        filesystem entries related to the session.

        The session title should be a human-readable string, as much as the
        application can create one, that describes the goal of the session.
        Some user interfaces will display this information.

        Using this method always creates a _new_ session. If the application
        intends to use session resuming functionality it should use other
        methods to see if session should be resumed instead.
        """
        assert self._manager is None, "session already started!"
        self._manager = SessionManager.create()
        self._context = self._manager.add_local_device_context()
        self._metadata = self._context.state.metadata
        self._metadata.app_id = self._app_id
        self._metadata.title = title
        self._metadata.flags = {'bootstrapping'}
        self._manager.checkpoint()

    def load_providers(self, *names):
        """
        Load plainbox providers.

        :param names:
            The list of names of providers to load.
        :returns:
            The list of loaded providers.
        :raises ValueError:
            If the name list is empty
        :raises ValueError:
            If any of the providers cannot be loaded.

        Load and add plainbox providers into an active session. A provider is
        used to supply tests (or in general, jobs) to execute.  Typically
        applications will have an associated, well-known provider that they
        wish to load.

        Providers can be broken and can, in fact, load in a partially or
        entirely damaged state. Applications should inspect the problem list of
        each loaded provider to see if they wish to abort.

        .. todo::
            Delegate correctness checking to a mediator class that also
            implements some useful, default behavior for this.
        """
        assert self._context is not None, "create a session first"
        assert self._provider_list is None, "providers already loaded"
        names = set(names)
        loaded = []
        if not names:
            raise ValueError("you should load at least one provider")
        self._provider_list = get_providers()
        # NOTE: providers are actually enumerated here, they are only
        # loaded and validated on demand so this is is not going to expose
        # any problems from utterly broken providers we don't care about.
        for provider in self._provider_list:
            if provider.name in names:
                names.remove(provider.name)
                self._context.add_provider(provider)
                loaded.append(provider)
        if names:
            raise ValueError("unknown providers: {}".format(
                ', '.join(sorted(names))))
        return loaded

    def select_test_plan(self, test_plan_id):
        """
        Select a test plan for execution.

        :param test_plan_id:
            The identifier of the test plan to execute.
        :raises ValueError:
            If the test plan with that identifier cannot be found.

        Test plans describe all of the essential details needed to execute a
        set of tests. Like other plainbox components each test plan has an
        unique identifier.

        Upon making the selection the application can inspect the execution
        plan which is expressed as a list of jobs to execute.
        """
        assert self._context is not None, "create a session first"
        for unit in self._context.unit_list:
            if unit.Meta.name == 'test plan':
                if unit.id == test_plan_id:
                    break
        else:
            raise ValueError("unknown test plan")
        self._manager.test_plans = (unit, )
        desired_job_list = select_jobs(
            self._context.state.job_list, [unit.get_qualifier()])
        self._context.state.update_desired_job_list(desired_job_list)
        self._metadata.flags = {'incomplete'}
        self._manager.checkpoint()

    def run_to_completion(self):
        assert self._context is not None, "create a session first"
        runner = JobRunner(
            self._manager.storage.location,
            self._context.provider_list,
            os.path.join(self._manager.storage.location, 'io-logs'),
            RunnerDelegate())
        todo = self._context.state.run_list
        if not todo:
            raise ValueError("nothing to to!")
        yield ('starting-all', todo)
        for job in todo:
            yield ('starting-job', job)
            self._metadata.running_job_name = job.id
            self._manager.checkpoint()
            job_state, job_result = run_job_if_possible(
                self._context.state, runner, self._config, job, ui=SilentUI())
            self._metadata.running_job_name = None
            self._manager.checkpoint()
            yield ('finished-job', job, job_state, job_result)
        yield ('finished-all')
        self._metadata.flags = {}
        self._manager.checkpoint()

    def export_to_transport(self, exporter_id, transport):
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
        :raises KeyError:
            When the exporter unit cannot be found.
        """
        exporter_unit = self._manager.exporter_map[exporter_id]
        exporter = exporter_unit.exporter_cls(exporter_unit=exporter_unit)
        exported_stream = io.BytesIO()
        exporter.dump_from_session_manager(self._manager, exported_stream)
        exported_stream.seek(0)
        return transport.send(exported_stream)


class RunnerDelegate:
    pass


class SilentUI(IJobRunnerUI):

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
