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
:mod:`plainbox.impl.exporter.json` -- JSON exporter
===================================================

.. warning::
    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import json

from plainbox.impl.exporter import SessionStateExporterBase


class JSONSessionStateExporter(SessionStateExporterBase):
    """
    Session state exporter creating JSON documents
    """

    OPTION_MACHINE_JSON = 'machine-json'

    SUPPORTED_OPTION_LIST = (SessionStateExporterBase.SUPPORTED_OPTION_LIST +
                             (OPTION_MACHINE_JSON,))

    def dump(self, data, stream):
        if self.OPTION_MACHINE_JSON in self._option_list:
            return json.dump(data, stream, ensure_ascii=False,
                             indent=None, separators=(',', ':'))
        else:
            return json.dump(data, stream, ensure_ascii=False, indent=4),
