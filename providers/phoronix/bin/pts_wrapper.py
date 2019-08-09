#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This program handles running tests from the Phoronix Test Suite.

When run normally the PTS batch-run command always returns 0, regardless
whether the test failed or not.
Goal here is to see if the test in fact finished successfully. This is done
by looking for composite.xml file in the test-results subdir of the PTS
files nest. If the file doesn't exist or doesn't have all the neccessary
elements, the test will be marked as failed.
"""
import os
import subprocess
import sys

from datetime import datetime
from xml.etree import ElementTree


class ObservedDirectory:
    """Look for files/dirs created/modified since the object's creation."""
    def __init__(self, path):
        self._observing_since = datetime.now()
        self._path = path

    def get_changed(self):
        """Yield file nodes changed since the object's creation."""

        for node in os.listdir(self._path):
            last_modified = os.stat(os.path.join(self._path, node)).st_mtime
            if last_modified > self._observing_since.timestamp():
                yield node


class PTSResultFile:
    """PTS result file parser that can check if a test completed."""
    def __init__(self, path):
        self._results = []
        try:
            tree = ElementTree.parse(os.path.join(path, 'composite.xml'))
            root = tree.getroot()
            for result in root.findall('Result'):
                self._parse_result_elem(result)

        except Exception:
            # if we have problem reading the xml then it means we don't have
            # any results
            pass

    def has_result_for(self, test_id):
        for tid, value in self._results:
            if tid.startswith(test_id) and value is not None:
                return True
        return False

    def _parse_result_elem(self, res_elem):
        try:
            test_id = res_elem.find('./Identifier').text
            value = res_elem.find('./Data/Entry/Value').text
            self._results.append((test_id, value))
        except AttributeError:
            # if we cannot get those two fields it means there is no proper
            # result values
            return


def main():
    """Program's entry point."""
    if len(sys.argv) != 2:
        raise SystemExit('Usage: pts_wrapper.py TEST_ID')
    ppd = os.environ.get('PLAINBOX_PROVIDER_DATA')
    if not ppd:
        raise SystemExit('PLAINBOX_PROVIDER_DATA is not set')
    pts_bin = os.path.join(ppd, 'phoronix-test-suite', 'phoronix-test-suite')
    test_id = sys.argv[1]
    pts_results_dir = os.path.join(
        os.environ.get('PTS_USER_PATH_OVERRIDE',
                       os.path.expanduser('~/.phoronix-test-suite')),
        'test-results')
    observer = ObservedDirectory(pts_results_dir)
    subprocess.run([pts_bin, 'batch-run', test_id], env=os.environ)
    for changed_dir in observer.get_changed():
        res_path = os.path.join(pts_results_dir, changed_dir)
        res_file = PTSResultFile(res_path)
        if res_file.has_result_for(test_id):
            print('Result for the test {} found in {}'.format(
                test_id, res_path))
            return True
    raise SystemExit('Result for the test {} not found'.format(test_id))


if __name__ == '__main__':
    main()
