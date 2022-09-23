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
This program handles the creation of a pdf report based on the result
files that Phoronix Test Suite generates.
"""

import os
import re
import shutil
import subprocess
import sys


class PTSBinary:
    """Class for handling PTS invocation."""
    def __init__(self):
        ppd = os.environ.get('PLAINBOX_PROVIDER_DATA')
        if not ppd:
            raise SystemExit('PLAINBOX_PROVIDER_DATA is not set')
        self._pts_bin = os.path.join(
            ppd, 'phoronix-test-suite', 'phoronix-test-suite')

    def merge_reports(self, results):
        """Merge existing result-files and get the merged report name."""
        # merge subcommand asks if the user wants to open the merged report in
        # the browser. Let's shove 'n' to its stdin.
        out = subprocess.check_output(
            [self._pts_bin, 'merge-results'] + results,
            env=os.environ,
            encoding=sys.stdout.encoding,
            input='n')
        regex = re.compile(r'Merged Results Saved To.*\/(.*)\/composite.xml')
        for line in out.splitlines():
            matches = regex.findall(line)
            if matches:
                return matches[0]
        return ''

    def export_to_pdf(self, result):
        """Render a pdf report and move it to the session's directory."""
        # potentially we may want to capture the output of the command below
        # to see where the report got saved. But today it's hardcoded to user's
        # home so there's no point...
        subprocess.check_output(
            [self._pts_bin, 'result-file-to-pdf', result],
            env=os.environ,
            encoding=sys.stdout.encoding)
        src = os.path.join(
            os.path.expanduser('~'), result.rstrip('/') + '.pdf')
        dst = os.path.join(
            os.environ.get('PLAINBOX_SESSION_SHARE'), 'results.pdf')
        print('Moving {} to {}'.format(src, dst))
        shutil.move(src, dst)


def get_mergable_results(path='.'):
    """
    Get a list of results that really can be merged.

    If the merge subcomand is done on half-baked results, PTS will complain
    about not being supplied with correct number of arguments. So let's handle
    this corner case here by generating proper list of mergable results.
    """
    results = []
    for node in os.listdir(path):
        if os.path.exists(os.path.join(path, node, 'composite.xml')):
            results.append(node)
    return results


def main():
    """Program's entry point."""
    pts = PTSBinary()
    results = get_mergable_results()
    if not results:
        raise SystemExit(
            "None of the PTS tests passed, so there will be no report")
    elif len(results) == 1:
        pts.export_to_pdf(results[0])
    else:
        merged_report = pts.merge_reports(results)
        pts.export_to_pdf(merged_report)


if __name__ == '__main__':
    main()
