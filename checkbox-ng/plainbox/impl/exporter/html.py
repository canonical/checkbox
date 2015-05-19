# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
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
:mod:`plainbox.impl.exporter.html`
==================================

HTML exporter for human consumption

.. warning::
    THIS MODULE DOES NOT HAVE A STABLE PUBLIC API
"""

from datetime import datetime

from plainbox import __version__ as version
from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter


class HTMLSessionStateExporter(Jinja2SessionStateExporter):
    """
    Session state exporter creating HTML documents.

    This exporter uses jinja2 template to create a HTML report.
    """
    def __init__(self, option_list=None, system_id=None, timestamp=None,
                 client_version=None, client_name='plainbox'):
        super().__init__("checkbox.html", option_list)

        # Generate a dummy system hash if needed
        if system_id is None:
            system_id = ""
        self._system_id = system_id
        # Generate a timestamp if needed
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        self._timestamp = timestamp
        # Use current version unless told otherwise
        if client_version is None:
            client_version = "{}.{}.{}".format(*version[:3])
        self._client_version = client_version
        # Remember client name
        self._client_name = client_name

    def dump_from_session_manager(self, session_manager, stream):
        """
        Extract data from session_manager and dump it into the stream.

        :param session_manager:
            SessionManager instance that manages session to be exported by
            this exporter
        :param stream:
            Byte stream to write to.

        """
        data = {
            'manager': session_manager,
            'options': self.option_list,
            'timestamp': self._timestamp,
            'client_version': self._client_version,
            'client_name': self._client_name
        }
        self.dump(data, stream)
