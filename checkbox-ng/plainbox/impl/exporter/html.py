# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
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
:mod:`plainbox.impl.exporter.html`
==================================

HTML exporter for human consumption

.. warning::
    THIS MODULE DOES NOT HAVE A STABLE PUBLIC API
"""

import logging
from string import Template

from lxml import etree as ET
from pkg_resources import resource_filename

from plainbox.impl.exporter.xml import  XMLSessionStateExporter


logger = logging.getLogger("plainbox.exporter.html")


class HTMLSessionStateExporter(XMLSessionStateExporter):
    """
    Session state exporter creating HTML documents.

    It basically applies an xslt to the XMLSessionStateExporter output.
    """

    def dump(self, data, stream):
        """
        Public method to dump the HTML report to a stream
        """
        root = self.get_root_element(data)
        self.xslt_filename = resource_filename(
            "plainbox", "data/report/checkbox.xsl")
        template_substitutions = {
                'PLAINBOX_ASSETS': resource_filename("plainbox", "data/")}
        with open(self.xslt_filename, encoding="UTF-8") as xslt_file:
            xslt_template = Template(xslt_file.read())
        xslt_data = xslt_template.substitute(template_substitutions)
        xslt_root = ET.XML(xslt_data)
        transformer = ET.XSLT(xslt_root)
        r_tree = transformer(root)
        stream.write(ET.tostring(r_tree, pretty_print=True))
