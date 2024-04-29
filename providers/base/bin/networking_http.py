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


class HTTPConnection:
    def __init__(self, url, max_retries: int = 3):
        """
        A class that will try to connect to `url` up to `max_retries` times
        using `wget`. Each time connection fails, the timeout parameter of
        wget raises (10s the first time, 20s the second time, then 30s...)
        """
        self.url = url
        self.max_retries = max_retries
        self.current_run = 1

    def http_connect(self):
        if self.current_run > self.max_retries:
            raise SystemExit("Failed to connect to {}!".format(self.url))
        timeout = self.current_run * 10
        print(
            "Trying to connect to {} (timeout: {}s, tentative {}/{})".format(
                self.url, timeout, self.current_run, self.max_retries
            )
        )
        try:
            subprocess.run(
                [
                    "wget",
                    "--timeout",
                    str(timeout),
                    "-SO",
                    "/dev/null",
                    self.url,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(exc)
            print()
            self.current_run += 1
            self.http_connect()


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL to try to connect to")
    parser.add_argument(
        "--retries",
        default="3",
        help="Number of connection tentatives to try (default %(default)s)",
    )
    args = parser.parse_args(args)
    connection_test = HTTPConnection(args.url, int(args.retries))
    connection_test.http_connect()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
