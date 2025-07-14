#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023-2025 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
This script updates a recipe on a given ppa with the objective of
updating the revision to build and the version of the package.

Note: This script uses the LP_CREDENTIALS environment variable
"""

import sys
import textwrap
import argparse

from utils import get_source_build_recipe, get_launchpad_client


def get_active_series():
    # this is hardcoded because supporting a new release requires a bit of manual
    # effort (copying support packages to the new series and doing the first build
    # dance of building packages in dependency order)
    desired_series = {
        "bionic",
        "focal",
        "jammy",
        "noble",
        "plucky",
        "questing",
    }
    lp = get_launchpad_client()
    active_series = {
        series.name for series in lp.projects["ubuntu"].series if series.active
    }

    outdated_series = desired_series - active_series
    if outdated_series:
        print(
            "The following series were desired but are now outdated:\n- ",
            end="",
        )
        print("\n- ".join(outdated_series))

    undesired_active = active_series - desired_series
    if undesired_active:
        print(
            "The following series weren't desired but are active:\n- ", end=""
        )
        print("\n- ".join(undesired_active))

    possible_series = desired_series & active_series
    api_formatter = "https://api.launchpad.net/devel/ubuntu/{}"
    return [api_formatter.format(x) for x in possible_series]


def get_build_path(recipe_name: str) -> str:
    # recipe name is in the form checkbox-{package}-{risk}
    package = recipe_name.split("-")[:-1]  # remove checkbox and risk
    if "provider" in recipe_name:
        component_name = "-".join(package[2:])  # 0-1 are checkbox provider
        return f"providers/{component_name}"
    elif "contrib" in recipe_name:
        component_name = "-".join(package[2:])  # 0-1 are checkbox contrib
        return f"contrib/{component_name}"
    return "-".join(package)


def get_updated_build_recipe(
    recipe_name: str,
    version: str,
    revision: str,
) -> str:
    target_path = get_build_path(recipe_name)
    new_recipe = textwrap.dedent(
        f"""
        # git-build-recipe format 0.4 deb-version {version}
        lp:~checkbox-dev/checkbox/+git/support empty
        nest-part packaging lp:~checkbox-dev/checkbox {target_path}/debian debian {revision}
        nest-part monorepo lp:~checkbox-dev/checkbox {target_path} {target_path} {revision}
        """
    ).strip()
    return new_recipe


def update_build_recipe(
    project_name: str,
    recipe_name: str,
    version: str,
    revision: str,
):
    lp_recipe = get_source_build_recipe(project_name, recipe_name)
    new_recipe = get_updated_build_recipe(recipe_name, version, revision)
    lp_recipe.recipe_text = new_recipe
    # this is important because while debugging, one may inadvertedly leave a
    # not-yet-working daily build enabled, this makes the daily builds fail for
    # no reason
    lp_recipe.distroseries = get_active_series()
    lp_recipe.lp_save()
    print(f"Updated build recipe: {lp_recipe.web_link}")
    print(new_recipe)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser("Update a recipe of a specific project")
    parser.add_argument("project", help="Unique name of the project")
    parser.add_argument(
        "--recipe", "-r", help="Recipe name to build with", required=True
    )
    parser.add_argument(
        "--new-version",
        "-n",
        help="New version to use in the recipe "
        "(for debian changelog) and bzr tags.",
        required=True,
    )
    parser.add_argument("--revision", help="Revision to build", required=True)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    update_build_recipe(
        args.project, args.recipe, args.new_version, args.revision
    )


if __name__ == "__main__":
    main(sys.argv[1:])
