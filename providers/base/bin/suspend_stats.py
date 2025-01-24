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
import argparse
import sys
import os


class SuspendStats:
    """
    This class is used to parse the information under
    /sys/power/suspend_stats/

    """

    contents = {}

    def __init__(self):
        suspend_stat_path = "/sys/power/suspend_stats/"
        self.contents = self.collect_content_under_directory(suspend_stat_path)

    def collect_content_under_directory(self, search_directory: str) -> dict:
        """
        Collect all content under specific directory by filename

        :param search_directory: The directory to search through.

        :returns: collected content by filename
        """
        content = {}
        for root, dirs, files in os.walk(search_directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                with open(
                    file_path, "r", encoding="utf-8", errors="ignore"
                ) as file:
                    content[file_name] = file.read().splitlines()[0]
        return content

    def print_all_content(self):
        """
        Print all contents under suspend_stats

        """
        for c in self.contents:
            print("{}:{}".format(c, self.contents[c]))

    def is_after_suspend(self) -> bool:
        """
        The system is under after suspend status or not

        :returns: return Ture while system is under after suspend status
        """
        return (
            self.contents["success"] != "0"
            and self.contents["failed_prepare"] == "0"
            and self.contents["failed_suspend"] == "0"
            and self.contents["failed_resume"] == "0"
        )

    def is_any_failed(self) -> bool:
        """
        Is any failed during suspend

        :returns: return Ture while one failed during suspend
        """
        return self.contents["fail"] != "0"

    def parse_args(self, args=sys.argv[1:]):
        """
        command line arguments parsing

        :param args: arguments from sys
        :type args: sys.argv
        """
        parser = argparse.ArgumentParser(
            prog="suspend status validator",
            description="Get and valid the content"
            "under /sys/power/suspend_stats/",
        )

        subparsers = parser.add_subparsers(dest="type")
        subparsers.required = True

        # Add parser for validating the system is after suspend or not
        parser_valid = subparsers.add_parser(
            "valid", help="validating the system is after suspend or not"
        )
        parser_valid.add_argument(
            "-p",
            "--print",
            dest="print",
            action="store_true",
            help="Print content",
        )
        # Add parser for printing last failed device
        parser_any = subparsers.add_parser(
            "any",
            help="Is there any failed during suspend",
        )
        parser_any.add_argument(
            "-p",
            "--print",
            dest="print",
            action="store_true",
            help="Print content",
        )

        return parser.parse_args(args)

    def main(self):
        args = self.parse_args()
        if args.type == "valid":
            if args.print:
                self.print_all_content()
            if not self.is_after_suspend():
                raise SystemExit("System is not under after suspend status")
        elif args.type == "any":
            if args.print:
                self.print_all_content()
            if self.is_any_failed():
                raise SystemExit(
                    "There are [{}] failed".format(self.contents["fail"])
                )


if __name__ == "__main__":
    SuspendStats().main()
