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

from string import Template
import base64
import logging
import mimetypes

from lxml import etree as ET
from pkg_resources import resource_filename

from plainbox.impl.exporter.xml import XMLSessionStateExporter


logger = logging.getLogger("plainbox.exporter.html")


class HTMLResourceInliner(object):
    """ A helper class to inline resources referenced in an lxml tree.
    """
    def _resource_content(self, url):
        try:
            with open(url, 'rb') as f:
                file_contents = f.read()
        except (IOError, OSError):
            logger.warning("Unable to load resource %s, not inlining",
                           url)
            return ""
        type, encoding = mimetypes.guess_type(url)
        if not encoding:
            encoding = "utf-8"
        if type in("text/css", "application/javascript"):
            return file_contents.decode(encoding)
        elif type in("image/png", "image/jpg"):
            b64_data = base64.b64encode(file_contents)
            b64_data = b64_data.decode("ascii")
            return_string = "data:{};base64,{}".format(type, b64_data)
            return return_string
        else:
            logger.warning("Resource of type %s unknown", type)
            #Strip it out, better not to have it.
            return ""

    def inline_resources(self, document_tree):
        """
        Replace references to external resources by an in-place (inlined)
        representation of each resource.

        Currently images, stylesheets and scripts are inlined.

        Only local (i.e. file) resources/locations are supported. If a
        non-local resource is requested for inlining, it will be removed
        (replaced by a blank string), with the goal that the resulting
        lxml tree will not reference any unreachable resources.

        :param document_tree:
            lxml tree to process.

        :returns:
            lxml tree with some elements replaced by their inlined
            representation.
        """
        # Try inlining using result_tree here.
        for node in document_tree.xpath('//script'):
            # These have  src attribute, need to remove the
            # attribute and add the content of the src file
            # as the node's text
            src = node.attrib.pop('src')
            node.text = self._resource_content(src)

        for node in document_tree.xpath('//link[@rel="stylesheet"]'):
            # These have a href attribute and need to be completely replaced
            # by a new <style> node with contents of the href file
            # as its text.
            src = node.attrib.pop('href')
            type = node.attrib.pop('type')
            style_elem = ET.Element("style")
            style_elem.attrib['type'] = type
            style_elem.text = self._resource_content(src)
            node.getparent().append(style_elem)
            # Now zorch the existing node
            node.getparent().remove(node)

        for node in document_tree.xpath('//img'):
            # src attribute points to a file and needs to
            # contain the base64 encoded version of that file.
            src = node.attrib.pop('src')
            node.attrib['src'] = self._resource_content(src)
        return document_tree


class HTMLSessionStateExporter(XMLSessionStateExporter):
    """
    Session state exporter creating HTML documents.

    It basically applies an xslt to the XMLSessionStateExporter output,
    and then inlines some resources to produce a monolithic report in a
    single file.
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
        return self.dump_etree(root,
                               stream,
                               xslt_template,
                               template_substitutions)

    def dump_etree(self, root, stream, xslt_template, template_substitutions):
        """
        Dumps the given lxml root tree into the given stream, by applying the
        provided xslt. If template_substitutions is provided, the xslt will
        first be processed as a string.Template with those substitutions.

        :param root:
            lxml root element of tree to process.

        :param stream:
            Byte stream into which to dump the resulting output.

        :param xslt_template:
            String containing an xslt with which to process the lxml
            tree to output the desired document type.

        :param template_substitutions:
            Dictionary with substitutions for variables which may be
            in the xslt_template.

        """
        if template_substitutions and isinstance(template_substitutions, dict):
            xslt_data = xslt_template.substitute(template_substitutions)
        xslt_root = ET.XML(xslt_data)
        transformer = ET.XSLT(xslt_root)
        r_tree = transformer(root)
        inlined_result_tree = HTMLResourceInliner().inline_resources(r_tree)
        stream.write(ET.tostring(inlined_result_tree, pretty_print=True))
