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

import logging
from threading import Thread
from io import BytesIO

from plainbox import __version__ as plainbox_version
from plainbox.abc import IJobResult
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session.state import SessionState


logger = logging.getLogger("plainbox.highlevel")


class Service:

    def __init__(self, provider_list, session_list):
        # TODO: session_list will be changed to session_manager_list
        self._provider_list = provider_list
        self._session_list = session_list

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

    def export_session_to_file(self, session, output_format, option_list, output_file):
        with open(output_file, 'wb') as f:
            self._export_session_to_stream(session, output_format,
                                       option_list, f)
        return output_file

    def _export_session_to_stream(self, session, output_format, option_list, stream):
        exporter_cls = get_all_exporters()[output_format]
        exporter = exporter_cls(option_list)
        data_subset = exporter.get_session_data_subset(session)
        exporter.dump(data_subset, stream)

    def _run(self, session, job, running_job_wrapper):
        """
        Start a JobRunner in a separate thread
        """
        runner = JobRunner(
            session.session_dir,
            session.jobs_io_log_dir,
            command_io_delegate=running_job_wrapper.ui_io_delegate,
            outcome_callback=running_job_wrapper.emitAskForOutcomeSignal
        )
        job_state = session.job_state_map[job.name]
        if job_state.can_start():
            job_result = runner.run_job(job)
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        if job_result is not None:
            running_job_wrapper.update_job_result_callback(job, job_result)

    def run_job(self, session, job, running_job_wrapper):
        runner = Thread(target=self._run,
                        args=(session, job, running_job_wrapper))
        runner.start()
        return job
