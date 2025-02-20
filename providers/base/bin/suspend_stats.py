#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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
from pathlib import Path
import argparse
import sys


class SuspendStats:
    """
    This class is used to parse the information under
    /sys/power/suspend_stats/

    """

    contents = {}

    def __init__(self):
        suspend_stat_path = "/sys/power/suspend_stats/"
        try:
            self.contents = self.collect_content_under_directory(
                suspend_stat_path
            )
        except FileNotFoundError:
            print(
                "There is no {}, use the information in debugfs".format(
                    suspend_stat_path
                )
            )
            self.contents = self.parse_suspend_stats_in_debugfs()

    def parse_suspend_stats_in_debugfs(self):
        """
        Collect needed content in /sys/kernel/debug/suspend_stats

        :param search_directory: The directory to search through.

        :returns: collected content by each line
        """
        debugfs = "/sys/kernel/debug/suspend_stats"
        content = {}

        with open(debugfs, "r") as d:
            for p in filter(None, (line.strip() for line in d.readlines())):
                if p != "failures:" and ":" in p:
                    kv = p.split(":")
                    if len(kv) > 1:
                        content[kv[0]] = kv[1].strip()
                    else:
                        content[kv[0]] = ""
        return content

    def collect_content_under_directory(self, search_directory: str) -> dict:
        """
        Collect all content under specific directory by filename

        :param search_directory: The directory to search through.

        :returns: collected content by filename
        """
        content = {}

        search_directory = Path(search_directory)
        for p in filter(lambda x: x.is_file(), search_directory.iterdir()):
            content[p.name], *_ = p.read_text().splitlines()
        return content

    def print_all_content(self):
        """
        Print all contents under suspend_stats

        """
        for c, v in self.contents.items():
            print("{}:{}".format(c, v))

    def is_after_suspend(self) -> bool:
        """
        The system is under after suspend status or not

        :returns: return Ture while system is under after suspend status
        """
        return self.contents["success"] != "0"

    def is_any_failed(self) -> bool:
        """
        Is any failed during suspend

        :returns: return Ture while one failed during suspend
        """
        for c, v in self.contents.items():
            if c.startswith("fail") and v != "0":
                return True
        return False

    def parse_args(self, args=sys.argv[1:]):
        """
        command line arguments parsing

        :param args: arguments from sys
        :type args: sys.argv
        """
        parser = argparse.ArgumentParser(
            prog="suspend status validator",
            description="Get and valid the content"
            "under /sys/power/suspend_stats/"
            "or /sys/kernel/debug/suspend_stats",
        )

        parser.add_argument(
            "check_type",
            help="The type to take e.g. after_suspend or any_failure.",
        )

        return parser.parse_args(args)

    def main(self):
        args = self.parse_args()
        self.print_all_content()
        if args.check_type == "after_suspend":
            if not self.is_after_suspend():
                raise SystemExit("System is not under after suspend status")
        else:
            if self.is_any_failed():
                raise SystemExit(
                    "There are [{}] failed".format(self.contents["fail"])
                )


if __name__ == "__main__":
    SuspendStats().main()
