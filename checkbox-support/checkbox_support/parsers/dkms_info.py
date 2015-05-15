# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json


class DkmsInfoResult():

    """A simple class to hold results for the DkmsInfoParser."""

    def __init__(self):
        self.dkms_info = {}

    def addDkmsInfo(self, pkg, details):
        self.dkms_info[pkg] = details


class DkmsInfoParser(object):

    """
    Parser for output from the dkms_info script.

    This is a very simple parser because the dkms_info script
    is designed to output json which we can simply json.loads().
    No attempt is made to hammer a noncompliant input into submission:
    if it doesn't json.load(), it's simply dropped on the floor.

    The name is slightly misleading as the dkms_info script also shows
    "non-dkms" packages which have a modaliases header (meaning they will
    be matched to specific devices) but don't provide an actual dkms module.
    """

    def __init__(self, stream):
        """
        Instantiate the parser with the stream to parse.

        :param stream: a file-like object in text-mode (so strings
        can be read directly from it)
        """
        self.stream = stream

    def run(self, result):
        """
        Parse the dkms_info output.

        Add each package found to the result instance. The addDkmsInfo method
        will be called with package, details.

        :param result: an object with an addDkmsInfo method.
        """
        try:
            data = json.loads(self.stream.read())
        except ValueError:
            # Return silently; result will be empty
            return
        # dkms output is a dict with lists of packages in each
        # "category". Category examples are "dkms" and "non-dkms".
        for kind, elements in data.items():
            # Elements can either be a list (for dkms) or a dict
            # keyed by package name (for non-dkms)
            try:
                # Assuming it's a dict...
                for package, data in elements.items():
                    # Validate that it contains at least
                    # modaliases and version, otherwise it's probably
                    # incomplete and useless information
                    if 'modaliases' in data and 'version' in data:
                        resdict = {'dkms-status': kind}
                        resdict.update(data)
                        result.addDkmsInfo(package, resdict)
            except AttributeError:
                # Oops, not a dict, maybe it's the list from dkms packages
                try:
                    for data in elements:
                        # Validate that it contains a dkms_name, dkms_ver,
                        # and pkg_name.
                        if all(k in data for k in ('dkms_name',
                                                   'dkms_ver',
                                                   'pkg_name')):
                            package = data['pkg_name']
                            resdict = {'dkms-status': kind}
                            resdict.update(data)
                            result.addDkmsInfo(package, resdict)
                except TypeError:
                    # Not a list either, ignore it silently.
                    pass


def parse_dkms_info(output):
    """
    Parse output of `dkms_info --format json`.

    :returns: no idea.
    """
    stream = io.StringIO(output)
    modparser = DkmsInfoParser(stream)
    result = DkmsInfoResult()
    modparser.run(result)
    return result
