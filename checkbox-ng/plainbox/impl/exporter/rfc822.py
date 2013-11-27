# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
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
:mod:`plainbox.impl.exporter.rfc822` -- RFC822 exporter
=======================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from collections import OrderedDict
from io import StringIO

from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.secure.rfc822 import RFC822Record


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
            RFC822Record(entry).dump(string_stream)
        stream.write(string_stream.getvalue().encode('UTF-8'))
