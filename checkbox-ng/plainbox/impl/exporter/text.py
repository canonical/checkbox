# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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

"""
:mod:`plainbox.impl.exporter.text` -- plain text exporter
=========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
from plainbox.impl.commands.inv_run import Colorizer
from plainbox.impl.exporter import SessionStateExporterBase


class TextSessionStateExporter(SessionStateExporterBase):
    """
    Human-readable session state exporter.
    """

    def __init__(self, color=None):
        self.C = Colorizer(color)

    def get_session_data_subset(self, session):
        return session

    def dump(self, session, stream):
        for job in session.run_list:
            state = session.job_state_map[job.id]
            if state.result.is_hollow:
                continue
            stream.write(
                "{:^15}: {}\n".format(
                    self.C.result(state.result), state.job.tr_summary(),
                ).encode("UTF-8"))
