# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.highlevel` -- High-level API
================================================
"""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Thread
import logging

from plainbox import __version__ as plainbox_version
from plainbox.abc import IJobResult
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session.legacy import SessionStateLegacyAPI as SessionState
from plainbox.impl.applogic import run_job_if_possible


logger = logging.getLogger("plainbox.highlevel")


class Service:

    def __init__(self, provider_list, session_list, config):
        # TODO: session_list will be changed to session_manager_list
        self._provider_list = provider_list
        self._session_list = session_list
        self._executor = ThreadPoolExecutor(1)
        self._config = config

    def close(self):
        self._executor.shutdown()

    @property
    def version(self):
        return "{}.{}.{}".format(*plainbox_version[:3])

    @property
    def provider_list(self):
        return self._provider_list

    @property
    def session_list(self):
        return self._session_list

    def create_session(self, job_list):
        # TODO: allocate storage
        # TODO: construct state
        # TODO: construct manager, binding storage and state
        # TODO: if something fails destroy storage
        session = SessionState(job_list)
        session.open()
        return session

    def get_all_exporters(self):
        return {name: exporter_cls.supported_option_list for
                name, exporter_cls in get_all_exporters().items()}

    def export_session(self, session, output_format, option_list):
        temp_stream = BytesIO()
        self._export_session_to_stream(session, output_format,
                                       option_list, temp_stream)
        return temp_stream.getvalue()

    def export_session_to_file(self, session, output_format, option_list,
                               output_file):
        with open(output_file, 'wb') as stream:
            self._export_session_to_stream(
                session, output_format, option_list, stream)
        return output_file

    def _export_session_to_stream(self, session, output_format, option_list,
                                  stream):
        exporter_cls = get_all_exporters()[output_format]
        exporter = exporter_cls(option_list)
        data_subset = exporter.get_session_data_subset(session)
        exporter.dump(data_subset, stream)

    def prime_job(self, session, job):
        """
        Prime the specified job for running.

        The job will be invoked in a context specific to the session.
        The configuration object associated with this service instance might be
        used to fetch any additional configuration data for certain jobs
        (environment variables)

        :returns: a primed job, ready to be started
        """
        return PrimedJob(self, session, job)


class PrimedJob:
    """
    Job primed for execution.
    """

    def __init__(self, service, session, job):
        """
        Initialize a primed job.

        This should not be called by applications.
        Please call :meth:`Service.prime_job()` instead.
        """
        self._service = service
        self._session = session
        self._job = job
        self._runner = JobRunner(
            session.session_dir,
            session.jobs_io_log_dir,
            # Pass a dummy IO delegate, we don't want to get any tracing here
            # Later on this could be configurable but it's better if it's
            # simple and limited rather than complete but broken somehow.
            command_io_delegate=self)

    @property
    def job(self):
        """
        The job to be executed
        """
        return self._job

    def run(self):
        """
        Run the primed job.

        :returns:
            Future for the job result

        .. note::
            This method returns immediately, before the job finishes running.
        """
        return self._service._executor.submit(self._really_run)

    def _really_run(self):
        """
        Internal method called in executor context.

        Runs a job with run_job_if_possible() and returns the result
        """
        # Run the job if possible
        job_state, job_result = run_job_if_possible(
            self._session, self._runner, self._service._config, self._job,
            # Don't call update on your own please
            update=False)
        return job_result
