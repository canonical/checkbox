#!/usr/bin/env python3
import sys
import time
import argparse
import textwrap
import itertools
from functools import wraps

from lazr.restfulclient.errors import BadRequest, ServerError

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

Read-only polling retries network timeouts, dropped connections, TLS errors
and HTTP (502/503/504) responses.
"""

# delay between updates requested to LP
LP_POLLING_DELAY = 60
LP_REQUEST_TIMEOUT_S = 30
LP_MAX_POLL_FAILURES = 10


def retry_polling(query):
    """Retry read-only queries without restarting or requesting builds."""

    @wraps(query)
    def wrapped(*args, **kwargs):
        for failure in range(1, LP_MAX_POLL_FAILURES + 1):
            delay = LP_POLLING_DELAY
            try:
                return query(*args, **kwargs)
            except TimeoutError:
                reason = "request timed out"
            # covers dropped connections and TLS errors (ssl.SSLError)
            except OSError as exc:
                reason = f"connection error: {exc}"
            except ServerError as exc:
                if exc.response.status not in (502, 503, 504):
                    raise
                reason = f"HTTP {exc.response.status}"
                retry_after = exc.response.get("retry-after")
                if retry_after is not None:
                    try:
                        delay = max(delay, int(retry_after))
                    except ValueError:
                        print(
                            f"Non-numeric Launchpad Retry-After: {retry_after!r}; "
                            f"using {delay}s"
                        )
            if failure == LP_MAX_POLL_FAILURES:
                raise SystemExit(
                    f"Launchpad polling failed {failure} consecutive times "
                    f"({reason})"
                )
            print(
                f"Launchpad polling failed ({reason}, "
                f"{failure}/{LP_MAX_POLL_FAILURES}); retrying in {delay}s"
            )
            time.sleep(delay)

    return wrapped


@retry_polling
def get_pending_builds(build_recipe):
    return build_recipe.getPendingBuildInfo()


@retry_polling
def get_build_state(build):
    build.lp_refresh()
    return build.buildstate


def get_recipe_version(build_recipe: LPSourcePackageRecipe) -> str:
    """
    Returns the version the recipe builds, read from its header line:
    # git-build-recipe format 0.4 deb-version <version>
    """
    header = build_recipe.recipe_text.splitlines()[0]
    return header.split("deb-version", 1)[1].strip()


@retry_polling
def get_series(build_recipe: LPSourcePackageRecipe, series_link: str):
    """
    Returns the series object of a recipe distroseries link
    (for example https://api.launchpad.net/devel/ubuntu/noble)
    """
    name = series_link.rstrip("/").rsplit("/", 1)[-1]
    distribution = build_recipe.daily_build_archive.distribution
    return distribution.getSeries(name_or_version=name)


@retry_polling
def is_version_published(
    build_recipe: LPSourcePackageRecipe, series, version: str
) -> bool:
    """
    Returns whether the recipe already uploaded this version for the series
    to the daily build archive. Launchpad rejects re-uploading it, even if
    the previous upload was deleted or superseded.
    """
    # Launchpad appends ~ubuntu<series version>.1 to the recipe version
    publications = build_recipe.daily_build_archive.getPublishedSources(
        source_name=recipe_name_to_source_name(build_recipe.name),
        distro_series=series,
        version=f"{version}~ubuntu{series.version}.1",
        exact_match=True,
    )
    return bool(list(publications))


def start_all_source_builds(build_recipe: LPSourcePackageRecipe):
    """
    Starts building a source recipe on all distro configured for it on
    launchpad targeting the default archive connected to the recipe
    (the daily build archive). Series where the recipe version is already
    published are skipped.
    """
    version = get_recipe_version(build_recipe)
    # distroseries is a list of API links, not series objects
    for series_link in build_recipe.distroseries:
        series = get_series(build_recipe, series_link)
        if is_version_published(build_recipe, series, version):
            print(
                f"{version} is already published for {series.name}, "
                "skipping its build"
            )
            continue
        try:
            build_recipe.requestBuild(
                pocket="Release",
                distroseries=series_link,
                archive=build_recipe.daily_build_archive_link,
            )
        except BadRequest:
            print("An identical build of this recipe is already pending")


def wait_every_source_build_started(build_recipe: LPSourcePackageRecipe):
    pending_builds = get_pending_builds(build_recipe)
    while pending_builds:
        print("Waiting some builds that are pending:")
        print(
            textwrap.indent(
                "-".join(build["distroseries"] for build in pending_builds),
                "  ",
            )
        )
        # avoid flooding LP with requests
        time.sleep(LP_POLLING_DELAY)
        pending_builds = get_pending_builds(build_recipe)


def print_builds(header: str, builds: list[LPBuild]):
    print(header)
    for build in builds:
        print(f"  {build.title}: {build.web_link}")


def recipe_name_to_source_name(name: str) -> str:
    """
    In Checkbox the recipe name is in the form of
    source-name-with-dashes-risk, this function removes risk
    """
    return name.rsplit("-", 1)[0]


@retry_polling
def get_source_publications(
    build_recipe: LPSourcePackageRecipe, started_datetime
) -> list:
    """
    Returns the source packages of the recipe published in the daily build
    archive since started_datetime (UTC+0)
    """
    return list(
        build_recipe.daily_build_archive.getPublishedSources(
            source_name=recipe_name_to_source_name(build_recipe.name),
            exact_match=True,
            created_since_date=started_datetime,
        )
    )


@retry_polling
def get_publication_builds(publication) -> list[LPBinaryBuild]:
    return list(publication.getBuilds())


@retry_polling
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
    source_recipe: LPSourcePackageRecipe,
    start_time,
    expected_publications: int,
) -> list[LPBinaryBuild]:
    """
    This function waits for the source packages built by the recipe since
    start_time to be published, then monitors their binary builds and reacts
    to them exactly as monitor_retry_builds does.

    Only the builds of this recipe are monitored, so builds of other
    packages in the same archive can't block this function.
    """
    source_name = recipe_name_to_source_name(source_recipe.name)
    publications = get_source_publications(source_recipe, start_time)
    while len(publications) < expected_publications:
        published = ", ".join(p.display_name for p in publications)
        print(
            f"Waiting for the {source_name} source packages to be published "
            f"({len(publications)}/{expected_publications}), "
            f"published so far: {published or 'none'}"
        )
        time.sleep(LP_POLLING_DELAY)
        publications = get_source_publications(source_recipe, start_time)

    # LP creates the binary builds when it accepts a source upload, so they
    # all exist once the source is published
    binary_builds = [
        build
        for publication in publications
        for build in get_publication_builds(publication)
    ]
    print_builds(
        f"Monitoring {len(binary_builds)} binary build(s):", binary_builds
    )
    return monitor_retry_builds(binary_builds)


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
    - Failed to upload -  note failure
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
        buildstate = get_build_state(build)
        if buildstate == "Successfully built":
            builds_ok.append(build)
        elif buildstate in [
            "Needs building",
            "Currently building",
            "Uploading build",
            "Gathering build output",
        ]:
            print(f"Build ongoing with status '{buildstate}': {build.title}")
            print(f"  weblink: {build.web_link}")
            # avoid flooding LP with requests
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
            print(f"Unknown build status '{buildstate}': {build.title}")
            print(f"  weblink: {build.web_link}")
            # avoid flooding LP with requests
            time.sleep(LP_POLLING_DELAY)
            builds_to_check.insert(0, build)
        # Failed to upload is basically always pointless to retry, as it
        # happens mostly when we have re-triggered a build that was already
        # uploaded previously
        elif build.can_be_retried and buildstate != "Failed to upload":
            print(f"Build failed with status '{buildstate}': {build.title}")
            print(f"  retrying: {build.web_link}")
            # avoid flooding LP with requests
            time.sleep(LP_POLLING_DELAY)
            build.retry()
            builds_to_check.insert(0, build)
        else:
            builds_unrecoverable.append(build)
            print(f"Build failed with status '{buildstate}': {build.title}")
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
    build_recipe = get_source_build_recipe(
        project_name, recipe_name, timeout=LP_REQUEST_TIMEOUT_S
    )

    start_all_source_builds(build_recipe)

    wait_every_source_build_started(build_recipe)
    source_builds = get_all_source_builds(build_recipe, start_time)
    print_builds(
        f"Monitoring {len(source_builds)} source build(s):", source_builds
    )
    # monitor_retry_builds consumes the list it receives
    builds_unrecoverable = monitor_retry_builds(list(source_builds))
    source_builds_ok = sum(
        build.buildstate == "Successfully built" for build in source_builds
    )

    builds_unrecoverable += monitor_retry_binary_builds(
        build_recipe, start_time, source_builds_ok
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
    try:
        build_monitor_recipe(
            args.project,
            args.recipe,
        )
    except TimeoutError as exc:
        raise SystemExit(f"Launchpad request timed out: {exc}") from None


if __name__ == "__main__":
    main(sys.argv[1:])
