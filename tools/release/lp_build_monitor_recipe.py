#!/usr/bin/env python3
import sys
import time
import argparse
import textwrap
import itertools

from lazr.restfulclient.errors import BadRequest

from utils import (
    get_source_build_recipe,
    get_date_utc_now,
    LPBuild,
    LPSourceBuild,
    LPBinaryBuild,
    LPSourcePackageRecipe,
)

"""
This script triggers a build on a recipe (for the platforms configured on LP),
monitoring the build process and automatically retrying any build
that fails. If Launchpad doesn't allow to retry a build, the script
will keep on monitoring the others, and then exit with a non-0 return
value.
"""

# delay between updates requested to LP
LP_POLLING_DELAY = 60


def start_all_source_builds(build_recipe: LPSourcePackageRecipe):
    """
    Starts building a source recipe on all distro configured for it on
    launchpad targeting the default archive connected to the recipe
    (the daily build archive)
    """
    for series in build_recipe.distroseries:
        try:
            build_recipe.requestBuild(
                pocket="Release",
                distroseries=series,
                archive=build_recipe.daily_build_archive_link,
            )
        except BadRequest:
            print("An identical build of this recipe is already pending")


def are_binary_builds_ongoing(build_recipe: LPSourcePackageRecipe) -> bool:
    """
    Returns whether there is any pending or ongoing build in the default
    archive connected to the build_recipe.
    """
    # Note: this is a different definition of pending than the one used in
    #       in the buildstatus enum, this means pending (as in: the build
    #       is ready to start but no worker was assigned to it yet) and
    #       building (as in: the build is ongoing).
    build_counters = build_recipe.daily_build_archive.getBuildCounters()
    return build_counters["pending"] > 0


def wait_every_source_build_started(build_recipe: LPSourcePackageRecipe):
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


def recipe_name_to_source_name(name: str) -> str:
    """
    In Checkbox the recipe name is in the form of
    source-name-with-dashes-risk, this function removes risk
    """
    return name.rsplit("-", 1)[0]


def get_all_binary_builds(
    build_recipe: LPSourcePackageRecipe, started_datetime
) -> list[LPBinaryBuild]:
    """
    Returns all builds of the current calculated recipe target
    started after started_date (UTC+0)
    """
    recipe_target = recipe_name_to_source_name(build_recipe.name)
    builds = build_recipe.daily_build_archive.getBuildRecords(
        source_name=recipe_target
    )

    # date_first_dispatched is filled in once a build is dispatched
    # and is the actual start time, it can be None if the build is
    # still waiting to get picked up by a builder
    return list(
        itertools.takewhile(
            lambda build: build.date_first_dispatched is None
            or build.date_first_dispatched >= started_datetime,
            builds,
        )
    )


def get_all_source_builds(
    build_recipe: LPSourcePackageRecipe, started_datetime
) -> list[LPSourceBuild]:
    """
    Returns all builds of a recipe since started_date (UTC+0)
    """
    # note build_recipe.builds is sorted from newer to older
    # using takewhile here saves quite a lot of time/requests to LP
    # because we don't get the full history of builds but just those that we
    # need
    return list(
        itertools.takewhile(
            lambda build: build.date_first_dispatched >= started_datetime,
            build_recipe.builds,
        )
    )


def monitor_retry_binary_builds(
    source_recipe: LPSourcePackageRecipe, start_time
) -> list[LPBinaryBuild]:
    """
    This function will monitor all binary builds in the default archive for
    a given recipe and react to them exactly as monitor_retry_builds does.

    This is different from monitor_retry_builds because it
    will keep monitoring for new builds till there is nothing pending or
    building in the archive. The reason this is done is that there does not
    seem to be a way to wait for all pending binary builds in an archive to
    start so we have no way of knowing when all pending builds actually
    started.
    """
    builds_unrecoverable = []
    start_checking_binary = start_time
    # source builds will trigger new binary build
    while are_binary_builds_ongoing(source_recipe):
        # to avoid a race condition, lets get the time at the beginning of the
        # iteration that we will use to filters binary builds the next iteration
        iteration_start_time = get_date_utc_now()

        # this filters the binary builds from start_checking_binary (the
        # beginning of the previous iteration or the latest pending build).
        # This is done because if a build was included in the previous
        # get_all_binary_builds it has been taken to completion
        # by monitor_retry_builds either failing it
        # completely or making it pass. What matters is that we don't
        # under-monitor, as re-getting the same build will deterministically
        # yield the same result resulting in the wcs. in a duplicated
        # builds_unrecoverable record
        binary_builds_to_check = get_all_binary_builds(
            source_recipe, start_checking_binary
        )
        builds_unrecoverable += monitor_retry_builds(binary_builds_to_check)
        start_checking_binary = iteration_start_time

        if not binary_builds_to_check:
            # this may be because all builds for this recipe are done, either
            # way lets not spam LP with requests
            time.sleep(LP_POLLING_DELAY)

    return builds_unrecoverable


def monitor_retry_builds(builds_to_check: list[LPBuild]) -> list[LPBuild]:
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

    This function returns the list of builds that didn't succeed and
    it was unable to retry
    """
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
            print(f"Build ongoing with status '{buildstate}'")
            print(f"  weblink: {build.web_link}")
            time.sleep(LP_POLLING_DELAY)
            builds_to_check.insert(0, build)
        elif buildstate not in [
            "Failed to build",
            "Dependency wait",
            "Chroot problem",
            "Failed to upload",
            "Build for superseded Source",
            "Cancelling build",
            "Cancelled build",
        ]:
            print(f"Unknown build status '{buildstate}'")
            print(f"  weblink: {build.web_link}")
            time.sleep(LP_POLLING_DELAY)
            builds_to_check.insert(0, build)
        elif build.can_be_retried:
            print(f"Build failed with status '{buildstate}'")
            print(f"  retrying: {build.web_link}")
            time.sleep(LP_POLLING_DELAY)
            build.retry()
            builds_to_check.insert(0, build)
        else:
            builds_unrecoverable.append(build)
            print(f"Build failed with status '{buildstate}' ")
            print(f"  unrecoverable: {build.web_link}")

    return builds_unrecoverable


def build_monitor_recipe(project_name: str, recipe_name: str):
    """
    This will start the recipe with the given name under the given project
    and trigger->(monitor and retry) any source build till they are either
    unrecoverably failed or successful, then (wait->monitor->retry-?>wait)
    any binary build that the source landing in the ppa will trigger till
    they all unrecoverably fail or succeed.

    This will raise SystemExit with a human readable message if any build
    unrecoverably fails.
    """
    start_time = get_date_utc_now()
    build_recipe = get_source_build_recipe(project_name, recipe_name)

    start_all_source_builds(build_recipe)

    wait_every_source_build_started(build_recipe)
    source_builds_to_check = get_all_source_builds(build_recipe, start_time)
    builds_unrecoverable = monitor_retry_builds(source_builds_to_check)

    builds_unrecoverable += monitor_retry_binary_builds(
        build_recipe, start_time
    )

    if builds_unrecoverable:
        weblinks_of_failed = "\n".join(
            build.web_link for build in builds_unrecoverable
        )
        raise SystemExit(
            "The following failed and can't be recovered\n"
            + textwrap.indent(weblinks_of_failed, "  ")
        )


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
