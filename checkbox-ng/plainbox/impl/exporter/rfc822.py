# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`plainbox.impl.exporter.rfc822` -- RFC822 exporter
=======================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from io import StringIO

from plainbox.impl.rfc822 import dump_rfc822_records
from plainbox.impl.exporter import SessionStateExporterBase
from collections import OrderedDict


class RFC822SessionStateExporter(SessionStateExporterBase):
    """
    Session state exporter creating rfc822 documents
    """

    def dump(self, data, stream):
        entry = OrderedDict()
        string_stream = StringIO()
        for job_name, job_data in sorted(data['result_map'].items()):
            entry['name'] = job_name
            entry.update(job_data)
            dump_rfc822_records(entry, string_stream)
        stream.write(string_stream.getvalue().encode('UTF-8'))
