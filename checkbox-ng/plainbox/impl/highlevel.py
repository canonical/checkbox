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

from plainbox import __version__ as plainbox_version
from plainbox.impl.exporter import get_all_exporters
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
        return SessionState(job_list)

    def get_all_exporters(self):
        return {name: exporter_cls.supported_option_list for
                name, exporter_cls in get_all_exporters().items()}

    def export_session(self, session, output_format, option_list, output_file):
        exporter_cls = get_all_exporters()[output_format]
        exporter = exporter_cls(option_list)
        data_subset = exporter.get_session_data_subset(session)
        with open(output_file, 'wb') as f:
            exporter.dump(data_subset, f)

    def run_job(self, session, job):
        # TODO: run the job for real
        raise NotImplementedError()
