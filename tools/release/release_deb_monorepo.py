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
import atexit
import tempfile
import subprocess

from pathlib import Path

from functools import partial
from contextlib import suppress

CONFIG_PPA_DEV_TOOLS = """{{
    'wait_max_age_hours' : 10,
    'exit_on_only_build_failure' : True,
    'wait_seconds' : 60,
    'name' : '{}'
}}
"""

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

def _del_file(path):
    with suppress(FileNotFoundError):
        os.remove(path)

def check_build(name) -> bool:
    """
    Checks if a build was succesful, returns true if it was
    """
    handle, path = tempfile.mkstemp(text=True)
    # try to remove the file before exit
    atexit.register(partial(_del_file, path))
    with os.fdopen(handle, "w") as f:
        f.write(CONFIG_PPA_DEV_TOOLS.format(name))
    with suppress(subprocess.CalledProcessError):
        subprocess.check_call(
            [
                "/tmp/ppa-dev-tools/scripts/ppa",
                "wait",
                "ppa:checkbox-dev/beta",
                "-C",
                path
            ]
        )
        return True
    return False

def main():
    """Update the PPA beta recipes and kick-off the builds."""
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
    to_check = []
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
            recipes_name = package_name + '-beta'
            output = run(
                "./tools/release/lp-recipe-update-build.py checkbox "
                "--recipe {} -n {}".format(
                    recipes_name, new_version),
                shell=True, check=True).stdout.decode().rstrip()
            print(output)
            to_check.append(package_name)

    checked = [(name, check_build(name)) for name in to_check]
    for name, ok in checked:
        if not ok:
            print("Failed to build:", name)
    if any(not ok for (_,ok) in checked):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
