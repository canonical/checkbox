#!/usr/bin/env python3
import sys
import time
import argparse
import textwrap
import itertools

from lazr.restfulclient.errors import BadRequest

from utils import get_build_recipe, get_date_utc_now

"""
This script triggers a build on a recipe (for the platforms configured on LP),
monitoring the build process and automatically retrying any build
that fails. If Launchpad doesn't allow to retry a build, the script
will keep on monitoring the others, and then exit with a non-0 return
value.
"""

# delay between updates requested to LP
LP_POLLING_DELAY = 60


def start_all_build(build_recipe):
    for series in build_recipe.distroseries:
        try:
            build_recipe.requestBuild(
                pocket="Release",
                distroseries=series,
                archive=build_recipe.daily_build_archive_link,
            )
        except BadRequest:
            print("An identical build of this recipe is already pending")


def wait_every_build_started(build_recipe):
    pending_builds = build_recipe.getPendingBuildInfo()
    while pending_builds:
        print("Waiting some builds that are pending:")
        print(
            textwrap.indent(
                "-".join(build["distroseries"] for build in pending_builds),
                "  ",
            )
        )
        time.sleep(LP_POLLING_DELAY)
        pending_builds = build_recipe.getPendingBuildInfo()


def get_new_builds(build_recipe, started_datetime):
    """
    Returns all builds of a recipe since started_date (UTC+0)
    """
    # note build_recipe.builds is sorted from newer to older
    # using takewhile here saves quite a lot of time/requests to LP
    # because we don't get the full history of builds but just those that we
    # need
    return list(
        itertools.takewhile(
            lambda build: build.date_first_dispatched > started_datetime,
            build_recipe.builds,
        )
    )


def monitor_retry_builds(build_recipe, start_date):
    """
    This function monitors the builds that were started after start_date

    This is how this function reacts to every build status:
    - Successfully built - ok
    - Needs building - wait
    - Currently building - wait
    - Gathering build output - wait
    - Uploading build - wait
    - Failed to build - retry or note failure
    - Dependency wait - retry or note failure
    - Chroot problem - retry or note failure
    - Failed to upload - retry or note failure
    - Build for superseded Source - retry or note failure
    - Cancelling build - retry or note failure
    - Cancelled build - retry or note failure

    If a build can not be retried, once the monitoring of the others
    is finished, this function will raise SystemExit with the list of
    failed builds
    """
    builds_to_check = get_new_builds(build_recipe, start_date)
    builds_unrecoverable = []
    builds_ok = []
    while builds_to_check:
        build = builds_to_check.pop()
        build.lp_refresh()
        buildstate = build.buildstate
        if buildstate == "Successfully built":
            builds_ok.append(build)
        elif buildstate in [
            "Needs building",
            "Currently building",
            "Uploading build",
            "Gathering build output",
        ]:
            # avoid flooding LP with requests
            time.sleep(LP_POLLING_DELAY)
            builds_to_check.insert(0, build)
            print(f"Build ongoing with status '{buildstate}'")
            print(f"  weblink: {build.web_link}")
        elif build.can_be_retried:
            time.sleep(LP_POLLING_DELAY)
            print(f"Build failed with status '{buildstate}'")
            print(f"  retrying: {build.web_link}")
            build.retry()
            builds_to_check.insert(0, build)
        else:
            builds_unrecoverable.append(build)
            print(f"Build failed with status '{buildstate}' ")
            print(f"  unrecoverable: {build.web_link}")

    if builds_unrecoverable:
        weblinks_of_failed = "\n".join(
            build.web_link for build in builds_unrecoverable
        )
        raise SystemExit(
            "The following failed and can't be recovered\n"
            + textwrap.indent(weblinks_of_failed, "  ")
        )


def build_monitor_recipe(project_name: str, recipe_name: str):
    start_time = get_date_utc_now()
    build_recipe = get_build_recipe(project_name, recipe_name)

    start_all_build(build_recipe)

    wait_every_build_started(build_recipe)

    monitor_retry_builds(build_recipe, start_time)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser("Update a recipe of a specific project")
    parser.add_argument("project", help="Unique name of the project")
    parser.add_argument("recipe", help="Recipe name to build with")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    build_monitor_recipe(
        args.project,
        args.recipe,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
