# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Exporter for creating the XML structure expected by HEXR."""

from datetime import datetime

from jinja2 import Markup
from jinja2 import Undefined
from jinja2 import environmentfilter
from jinja2 import escape

from plainbox import __version__ as version
from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter
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


class HEXRExporter(Jinja2SessionStateExporter):

    """
    Exporter for creating HEXR XML documents.

    This exporter takes the whole session and creates a XML document
    containing a subset of the data. It is applicable for submission to HEXR
    and ``C3`` (the certification website). It's also really bad.

    The format is hardwired to require certain jobs. They are:

    - 2013.com.canonical.certification::package          (Optional)
    - 2013.com.canonical.certification::uname            (Optional)
    - 2013.com.canonical.certification::lsb              (Mandatory)
    - 2013.com.canonical.certification::cpuinfo          (Mandatory)
    - 2013.com.canonical.certification::dpkg             (Mandatory)
    - 2013.com.canonical.certification::dmi_attachment   (Mandatory)
    - 2013.com.canonical.certification::sysfs_attachment (Mandatory)
    - 2013.com.canonical.certification::udev_attachment  (Mandatory)

    .. note::
        The exporter won't misbehave if those are not available but the server
        side component will most likely crash or reject the resulting document.
    """

    def __init__(self, option_list=None, system_id="", timestamp=None,
                 client_version=None, client_name='plainbox'):
        """Initialize the exporter with stuff that exporters need."""
        super().__init__("hexr.xml", option_list)
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

    def customize_environment(self, env):
        """Register filters and tests custom to the HEXR exporter."""
        env.autoescape = True
        env.filters['sorted_xmlattr'] = do_sorted_xmlattr
        env.filters['strip_ns'] = do_strip_ns
        env.tests['is_name'] = do_is_name

    def dump_from_session_manager(self, manager, stream):
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
            'manager': manager,
            'options': self.option_list,
            'system_id': self._system_id,
            'timestamp': self._timestamp,
        }
        self.dump(data, stream)
