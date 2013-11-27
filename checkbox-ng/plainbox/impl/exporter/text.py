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


from plainbox.impl.exporter import SessionStateExporterBase


class TextSessionStateExporter(SessionStateExporterBase):
    """
    Human-readable session state exporter.
    """

    def dump(self, data, stream):
        for job_name, job_data in sorted(data['result_map'].items()):
            stream.write("{}: {}\n".format(
                job_name, job_data['outcome']).encode('UTF-8'))
