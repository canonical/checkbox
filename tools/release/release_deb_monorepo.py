#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2022-2023 Canonical Ltd.
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

import os
import subprocess

from pathlib import Path


def run(*args, **kwargs):
    """wrapper for subprocess.run."""
    try:
        return subprocess.run(
            *args, **kwargs,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print('{}\n{}'.format(e, e.output.decode()))
        raise SystemExit(1)


def main():
    """Update the PPA testing recipes and kick-off the builds."""
    # Request code import
    staging = ""
    if os.getenv("CHECKBOX_REPO", "").endswith("staging"):
        staging = "-staging"
    print("Start code import...")
    output = run(
        "./tools/release/lp-request-import.py {}".format(
            "~checkbox-dev/checkbox/+git/checkbox"+staging),
        shell=True, check=True).stdout.decode().rstrip()
    print(output)
    for path, dirs, files in os.walk('.'):
        if "debian" in dirs:
            project_path = str(Path(*Path(path).parts))
            package_name = str(project_path).replace('s/', '-')
            if package_name.startswith('provider'):
                package_name = "checkbox-"+package_name
            if os.getenv("CHECKBOX_REPO", "").endswith("staging"):
                package_name = "staging-"+package_name
            cmd = run([
                'git', 'describe', '--tags',
                '--abbrev=0', '--match', 'v*'])
            new_version = cmd.stdout.decode().rstrip().split('v')[1]
            print("Request {} build ({})".format(
                package_name, new_version))
            output = run(
                "./tools/release/lp-recipe-update-build.py checkbox "
                "--recipe {} -n {}".format(
                    package_name+'-testing', new_version),
                shell=True, check=True).stdout.decode().rstrip()
            print(output)


if __name__ == "__main__":
    main()
