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

import json
import re
from collections import OrderedDict
from datetime import datetime

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import Markup
from jinja2 import environmentfilter
from jinja2 import escape

from plainbox import get_version_string
from plainbox.abc import ISessionStateExporter
from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.result import OUTCOME_METADATA_MAP
from plainbox.impl.unit.exporter import ExporterError


#: Name-space prefix for Canonical Certification
CERTIFICATION_NS = 'com.canonical.certification::'


@environmentfilter
def do_strip_ns(_environment, unit_id, ns=CERTIFICATION_NS):
    """Remove the namespace part of the identifier."""
    # com.my.namespace::category/job-id → category/job-id
    rv = unit_id.split("::")[-1]
    rv = escape(rv)
    if _environment.autoescape:
        rv = Markup(rv)
    return rv


def do_is_name(text):
    """A filter for checking if something is equal to "name"."""
    return text == 'name'


def json_load_ordered_dict(text):
    """Render json dict in Jinja templates but keep keys ordering."""
    return json.loads(
        text, object_pairs_hook=OrderedDict)


def highlight_keys(text):
    """A filter for rendering keys as bold html text."""
    return re.sub('(\w+:\s)', r'<b>\1</b>', text)


class Jinja2SessionStateExporter(SessionStateExporterBase):

    """Session state exporter that renders output using jinja2 template."""

    supported_option_list = ('without-session-desc')

    def __init__(self, option_list=None, system_id="", timestamp=None,
                 client_version=None, client_name='plainbox',
                 exporter_unit=None):
        """
        Initialize a new Jinja2SessionStateExporter with given arguments.
        """
        super().__init__((), exporter_unit=exporter_unit)
        self._unit = exporter_unit
        self._system_id = system_id
        # Generate a time-stamp if needed
        self._timestamp = (
            timestamp or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
        # Use current version unless told otherwise
        self._client_version = client_version or get_version_string()
        # Remember client name
        self._client_name = client_name

        self.option_list = None
        self.template = None
        self.data = dict()
        paths = []
        if exporter_unit:
            self.data = exporter_unit.data
            # Add PROVIDER_DATA to the list of paths where to look for
            # templates
            paths.append(exporter_unit.data_dir)
        if "extra_paths" in self.data:
            paths.extend(self.data["extra_paths"])
        self.option_list = tuple(exporter_unit.option_list or ()) + tuple(
                option_list or ())
        loader = FileSystemLoader(paths)
        env = Environment(loader=loader, extensions=['jinja2.ext.autoescape'])
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
        """Register filters and tests custom to the JSON exporter."""
        env.autoescape = True
        env.filters['jsonify'] = json.dumps
        env.filters['strip_ns'] = do_strip_ns
        env.filters['json_load_ordered_dict'] = json_load_ordered_dict
        env.filters['highlight_keys'] = highlight_keys
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
        try:
            state = self._trim_session_manager(session_manager).state
            app_blob = state.metadata.app_blob
            app_blob_data = json.loads(app_blob.decode("UTF-8"))
        except ValueError:
            app_blob_data = {}
        data = {
            'OUTCOME_METADATA_MAP': OUTCOME_METADATA_MAP,
            'client_name': self._client_name,
            'client_version': self._client_version,
            'manager': session_manager,
            'app_blob': app_blob_data,
            'options': self.option_list,
            'system_id': self._system_id,
            'timestamp': self._timestamp,
        }
        data.update(self.data)
        self.dump(data, stream)
        self.validate(stream)

    def dump_from_session_manager_list(self, session_manager_list, stream):
        """
        Extract data from session_manager_list and dump them into the stream.

        :param session_manager_list:
            SessionManager instances that manages session to be exported by
            this exporter
        :param stream:
            Byte stream to write to.

        """
        data = {
            'OUTCOME_METADATA_MAP': OUTCOME_METADATA_MAP,
            'client_name': self._client_name,
            'client_version': self._client_version,
            'manager_list': session_manager_list,
            'app_blob': {},
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

    def validate(self, stream):
        # we need to validate the whole thing from the beginning
        pos = stream.tell()
        stream.seek(0)
        validator_fun = {
            'json': self.validate_json,
        }.get(self.unit.file_extension, lambda *_: [])
        problems = validator_fun(stream)
        # XXX: in case of problems we don't really need to .seek() back
        # but let's be safe
        stream.seek(pos)
        if problems:
            raise ExporterError(problems)

    def validate_json(self, stream):
        """
        Returns a list of things wrong that made the validation fail.
        """
        # keeping it as a method to make it tidy and consistent with
        # any other possible validator that may use self
        try:
            # manually reading the stream to ensure decoding
            raw = stream.read()
            s = raw.decode('utf-8') if type(raw) == bytes else raw
            json.loads(s)
            return []
        except Exception as exc:
            return [str(exc)]
