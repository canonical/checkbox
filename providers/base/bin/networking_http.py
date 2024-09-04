#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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
#

import argparse
import subprocess
import sys

from checkbox_support.helpers.retry import retry


@retry
def http_connect(url):
    """
    Use `wget` to try to connect to `url`. If attempt fails, the next one is
    made after adding a random delay calculated using a backoff and a jitter
    (with a maximum delay of 60 seconds).
    """
    subprocess.run(
        [
            "wget",
            "-SO",
            "/dev/null",
            url,
        ],
        check=True,
    )


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL to try to connect to")
    args = parser.parse_args(args)
    http_connect(args.url)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
