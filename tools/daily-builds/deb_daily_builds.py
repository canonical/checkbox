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
                "ppa:checkbox-dev/ppa",
                "-C",
                path
            ]
        )
        return True
    return False

def main():
    """Parse the checkbox monorepo to trigger deb daily builds in Launchpad."""
    # First request code import (GitHub -> Launchpad)
    run(
       "./tools/release/lp-request-import.py "
       "~checkbox-dev/checkbox/+git/checkbox",
       shell=True, check=True)
    projects = {}
    for path, dirs, files in os.walk('.'):
        if "debian" in dirs:
            project_path = os.path.relpath(path)
            # Tweak the provider paths to get names in the following form:
            # providers/base -> checkbox-provider-base
            project_name = project_path.replace('s/', '-')
            if project_name.startswith('provider'):
                project_name = "checkbox-"+project_name
            projects[project_name] = project_path
    to_check = []
    # Find projects new commits from the last 24 hours
    for name, path in sorted(projects.items(), key=lambda i: i[1]):
        new_commits = int(run(
            'git rev-list --count HEAD --not '
            '$(git rev-list -n1 --before="24 hours" '
            '--first-parent HEAD) -- :{}'.format(path),
            shell=True, check=True).stdout.decode().rstrip())
        # Kick off daily builds if the new commits got merged into main
        if new_commits:
            output = run(
                "./tools/daily-builds/lp-recipe-build.py checkbox "
                "--recipe {}".format(name+'-daily'),
                shell=True, check=True).stdout.decode().rstrip()
            print(output)
            # We have started the build, store it here so it can
            # be checked after.
            to_check.append(name)

    checked = [(name, check_build(name)) for name in to_check]
    for name, ok in checked:
        if not ok:
            print("Failed to build:", name)
    if any(not ok for (_,ok) in to_check):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
