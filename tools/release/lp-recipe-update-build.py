#!/usr/bin/python3
# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
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

"""
Kicks off a recipe build for a branch in Launchpad which has an associated
recipe.
Meant to be used as part of a checkbox release to the Hardware Certification
public PPA and the ~checkbox-dev testing PPA.
"""

import os
import re
import sys

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.errors import BadRequest
from argparse import ArgumentParser


def main():
    parser = ArgumentParser('Invoke a recipe build on specified branch')
    parser.add_argument('project',
                        help="Unique name of the project")
    parser.add_argument('--recipe', '-r',
                        help="Recipe name to build with. If there is only one "
                             "then that will be used by default, if not then "
                             "this must be specified.")
    parser.add_argument('--new-version', '-n',
                        help="New version to use in the recipe "
                             "(for debian changelog) and bzr tags.")
    args = parser.parse_args()

    credentials = Credentials.from_string(os.getenv("LP_CREDENTIALS"))
    lp = Launchpad(
        credentials, None, None, service_root='production', version='devel')
    try:
        project = lp.projects[args.project]
    except KeyError:
        parser.error("{} was not found in Launchpad.".format(args.project))

    if project.recipes.total_size == 0:
        parser.error("{} does not have any recipes.".format(args.project))
    else:
        build_recipe = None

        if project.recipes.total_size == 1:
            build_recipe = project.recipes[0]
        elif args.recipe:
            for recipe in project.recipes:
                if recipe.name == args.recipe:
                    build_recipe = recipe
        else:
            all_recipe_names = [recipe.name for recipe in project.recipes]
            parser.error(
                "I don't know which recipe from "
                "{project} you want to use, specify "
                "one of '{recipes}' using --recipe".format(
                    project=args.project,
                    recipes=', '.join(all_recipe_names)))

        text = build_recipe.recipe_text
        # 0.28.0rc1 → 0.28.0~rc1
        deb_version = re.sub(r"(rc\d+)$", "~\g<0>", args.new_version)
        # 0.28.0rc1 → 0.28.0_rc1
        deb_tag = re.sub(r"(rc\d+)$", "_\g<0>", args.new_version)
        text = re.sub(r"deb-version .*?~ppa", "deb-version {}~ppa".format(
            deb_version), text)
        # v0.27.0 → v0.28.0rc1
        text = re.sub(r"v\d\S+", "v{}".format(args.new_version), text)
        # debian-0.27.0-1 → debian-0.28.0_rc1-1
        text = re.sub(r"debian-(.*)$", "debian-{}-1".format(deb_tag), text)
        build_recipe.recipe_text = text
        build_recipe.lp_save()
        if build_recipe:
            for series in build_recipe.distroseries:
                try:
                    build_recipe.requestBuild(
                        pocket="Release",
                        distroseries=series,
                        archive=build_recipe.daily_build_archive_link)
                except BadRequest:
                    print("An identical build of this recipe is "
                          "already pending")
        print("Check builds status: " + build_recipe.web_link)


if __name__ == "__main__":
    sys.exit(main())
