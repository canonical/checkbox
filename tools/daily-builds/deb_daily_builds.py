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


if __name__ == "__main__":
    main()
