# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

from datetime import datetime

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import Markup
from jinja2 import Undefined
from jinja2 import environmentfilter
from jinja2 import escape

from plainbox import __version__ as version
from plainbox.abc import ISessionStateExporter
from plainbox.i18n import gettext as _
from plainbox.impl.result import OUTCOME_METADATA_MAP


#: Name-space prefix for Canonical Certification
CERTIFICATION_NS = '2013.com.canonical.certification::'


@environmentfilter
def do_sorted_xmlattr(_environment, d, autospace=True):
    """A version of xmlattr filter that sorts attributes."""
    rv = ' '.join(
        '%s="%s"' % (escape(key), escape(value))
        for key, value in sorted(d.items())
        if value is not None and not isinstance(value, Undefined)
    )
    if autospace and rv:
        rv = ' ' + rv
    if _environment.autoescape:
        rv = Markup(rv)
    return rv


@environmentfilter
def do_strip_ns(_environment, unit_id, ns=CERTIFICATION_NS):
    """Remove the namespace part of the identifier."""
    if unit_id.startswith(ns):
        rv = unit_id[len(ns):]
    else:
        rv = unit_id
    rv = escape(rv)
    if _environment.autoescape:
        rv = Markup(rv)
    return rv


def do_is_name(text):
    """A filter for checking if something is equal to "name"."""
    return text == 'name'


class Jinja2SessionStateExporter(ISessionStateExporter):

    """Session state exporter that renders output using jinja2 template."""

    supported_option_list = ()

    def __init__(self, option_list=None, system_id="", timestamp=None,
                 client_version=None, client_name='plainbox',
                 exporter_unit=None):
        """
        Initialize a new Jinja2SessionStateExporter with given arguments.
        """
        self._unit = exporter_unit
        self._system_id = system_id
        # Generate a time-stamp if needed
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        self._timestamp = timestamp
        # Use current version unless told otherwise
        if client_version is None:
            client_version = "{}.{}.{}".format(*version[:3])
        self._client_version = client_version
        # Remember client name
        self._client_name = client_name
        
        self.option_list = None
        self.template = None
        self.data = dict()
        paths=[]
        if exporter_unit:
            self.data = exporter_unit.data
            # Add PROVIDER_DATA to the list of paths where to look for
            # templates
            paths.append(exporter_unit.data_dir)
        if "extra_paths" in self.data:
            paths.extend(self.data["extra_paths"])
        self.option_list = exporter_unit.option_list
        loader = FileSystemLoader(paths)
        env = Environment(loader=loader)
        self.customize_environment(env)

        def include_file(name):
            # This helper function insert static files literally into Jinja
            # templates without parsing them.
            return Markup(loader.get_source(env, name)[0])

        env.globals['include_file'] = include_file
        self.template = env.get_template(exporter_unit.template)

    @property
    def unit(self):
        """
        Exporter unit this exporter was created with.

        The exporter unit holds additional information that may be of use to
        applications, such as typical file name extension.
        """
        return self._unit

    def customize_environment(self, env):
        """Register filters and tests custom to the HEXR exporter."""
        env.autoescape = True
        env.filters['sorted_xmlattr'] = do_sorted_xmlattr
        env.filters['strip_ns'] = do_strip_ns
        env.tests['is_name'] = do_is_name

    def dump(self, data, stream):
        """
        Render report using jinja2 and dump it to stream.

        :param data:
            Dict to be used when rendering template instance
        :param stream:
            Byte stream to write to.

        """
        self.template.stream(data).dump(stream, encoding='utf-8')

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
            'OUTCOME_METADATA_MAP': OUTCOME_METADATA_MAP,
            'client_name': self._client_name,
            'client_version': self._client_version,
            'manager': session_manager,
            'options': self.option_list,
            'system_id': self._system_id,
            'timestamp': self._timestamp,
        }
        data.update(self.data)
        self.dump(data, stream)

    def get_session_data_subset(self, session_manager):
        """Compute a subset of session data."""
        return {
            'manager': session_manager,
            'options': self.option_list,
        }
