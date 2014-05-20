# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from subprocess import check_output, CalledProcessError
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import argparse
import os
import re


def check_log(logfile):
    """
    Read and check logfile in search for the pattern 'Benchmark_Score'.

    Returns:
        False if the pattern was found

    Raises:
        SystemExit if the pattern (or logfile) was not found
    """
    try:
        with open(logfile, encoding='utf-8', errors='ignore') as f:
            log = f.read()
            print(re.sub('^.*?>> ', '', log, flags=re.M))
            # Try to find the score in the log file,
            # otherwise something went wrong...
            if not re.search('Benchmark_Score', log):
                raise SystemExit(
                    'Benchmark score not found, check the log for errors')
    except EnvironmentError as error:
        raise SystemExit(error)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('test', metavar='TEST', help='test type',
                        choices=['fur', 'gi', 'tess'])
    parser.add_argument('--width',
                        help='window width', default=1024, type=int)
    parser.add_argument('--height',
                        help='window height', default=640, type=int)
    parser.add_argument('-f', '--fullscreen', action='store_true')
    parser.add_argument('-d', '--duration', default=60, type=int,
                        help='duration in s')
    parser.add_argument(
        '-p', '--path', help='GpuTest archive path',
        default='/opt/gputest-0.2.0/GpuTest_Linux_x64_20121111.zip'
    )
    args = parser.parse_args()

    # Unzip the archive in a temporary directory, GpuTest creates the log file
    # in the same place Gputest.exe is. A user-writable location is needed.
    with TemporaryDirectory() as scratch_dir:
        with ZipFile(args.path, 'r') as z:
            z.extractall(path=scratch_dir)
        dirname = os.path.join(scratch_dir, 'GpuTest_Linux_x64')
        launcher = os.path.join(dirname, 'GpuTest.exe')
        logfile = os.path.join(dirname, '_geeks3d_gputest_log.txt')
        os.chmod(launcher, 0o755)
        os.unlink(logfile)

        timeout_params = [
            'timeout',
            '-k',
            # Adds 16 s for the Warm-up phase before sending the KILL signal
            # See TIMEOUT(1)
            '{}'.format(args.duration + 16),
            # Adds 15 s for the Warm-up phase before sending the TERM signal
            '{}'.format(args.duration + 15),
            launcher
        ]
        cmd_params = [
            '/test={}'.format(args.test),
            '/width={}'.format(args.width),
            '/height={}'.format(args.height),
            '/benchmark_duration_ms={}'.format(args.duration * 1000)
        ]
        if args.fullscreen:
            cmd_params = cmd_params + ['/fullscreen']

        try:
            check_output(timeout_params + cmd_params, cwd=dirname)
        except CalledProcessError:
            # GpuTest.exe never returns, so the timeout exit code is always
            # set to a non-zero value. It's expected.
            pass
        return check_log(logfile)
