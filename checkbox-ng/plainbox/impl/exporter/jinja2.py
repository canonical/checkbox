# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
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
:mod:`plainbox.impl.exporter.jinja2` -- exporter using jinja2 templates
=======================================================================

.. warning::
    THIS MODULE DOES NOT HAVE A STABLE PUBLIC API
"""

from jinja2 import Template

from plainbox.abc import ISessionStateExporter


class Jinja2SessionStateExporter(ISessionStateExporter):

    """Session state exporter that renders output using jinja2 template."""

    def __init__(self, option_list=None, jinja2_template=""):
        """
        Initialize a new Jinja2SessionStateExporter with given arguments.

        :param option_list:
            List of options that template might use to fine-tune rendering.
        :param jinja2_template:
            String with Jinja2 template that will be used.

        """
        self.option_list = option_list
        self.template = Template(jinja2_template)

    def dump(self, data, stream):
        """
        Render report using jinja2 and dump it to stream.

        :param data:
            Dict to be used when rendering template instance
        :param stream:
            Byte stream to write to.

        """
        stream.write(self.template.render(data).encode('UTF-8'))

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
        }
        self.dump(data, stream)

    def get_session_data_subset(self, session_manager):
        """Compute a subset of session data."""
        return {
            'manager': session_manager,
            'options': self.option_list,
        }

    def supported_option_list(cls):
        """ Return list of supported exporter options."""
        return []
