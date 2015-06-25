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
from plainbox.i18n import gettext as _
from plainbox.impl.color import Colorizer
from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.result import outcome_meta


class TextSessionStateExporter(SessionStateExporterBase):

    """Human-readable session state exporter."""

    def __init__(self, option_list=None, color=None, exporter_unit=None):
        super().__init__(option_list, exporter_unit=exporter_unit)
        self.C = Colorizer(color)

    def get_session_data_subset(self, session_manager):
        return session_manager.state

    def dump(self, session, stream):
        for job in session.run_list:
            state = session.job_state_map[job.id]
            if state.result.is_hollow:
                continue
            if self.C.is_enabled:
                stream.write(
                    " {}: {}\n".format(
                        self.C.custom(
                            outcome_meta(state.result.outcome).unicode_sigil,
                            outcome_meta(state.result.outcome).color_ansi
                        ), state.job.tr_summary(),
                    ).encode("UTF-8"))
                if len(state.result_history) > 1:
                    stream.write(_("  history: {0}\n").format(
                        ', '.join(
                            self.C.custom(
                                result.outcome_meta().tr_outcome,
                                result.outcome_meta().color_ansi)
                            for result in state.result_history)
                    ).encode("UTF-8"))
            else:
                stream.write(
                    "{:^15}: {}\n".format(
                        state.result.tr_outcome(),
                        state.job.tr_summary(),
                    ).encode("UTF-8"))
                if state.result_history:
                    print(_("History:"), ', '.join(
                        self.C.custom(
                            result.outcome_meta().unicode_sigil,
                            result.outcome_meta().color_ansi)
                        for result in state.result_history))
