"""
This module contains various shared utils function used in
multiple release scripts
"""
import os
import datetime

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad

from lazr.restfulclient.resource import Entry


class LPObjects(Entry):
    """
    This object rappresents the result of a query using launchpadlib. This
    was introduced here for three reasons:
    - To track what each function returns
    - To reconstruct what the returned object is capable of
    - To track the ducky typing relation between these objects

    For this reason each subclass of this class will contain a link to the
    webapi documentation, because that is what launchpadlib actually uses.
    You can expect each row in the `Default representation (application/json)`
    table to be an attribute of the class, all Custom XX methods are functions
    of the class and some XX_link attributes also have an XX field that
    resolves to the XX object.

    Ex. build.daily_build_archive_link is the link to the daily build archive
        build.daily_build_archive is the daily build archive itself (an object
            of type archive)

    Documentation: https://launchpad.net/+apidoc/devel.html
    """

LPBuild = LPObjects

class LPSourceBuild(LPBuild):
    """
    Documentation: https://api.launchpad.net/devel/#source_package_recipe_build
    """

class LPBinaryBuild(LPBuild):
    """
    Documentation: https://api.launchpad.net/devel/#build
    """

class LPSourcePackageRecipe(Entry):
    """
    Documentation: https://api.launchpad.net/devel/#source_package_recipe
    """


def get_launchpad_client() -> Launchpad:
    credentials = os.getenv("LP_CREDENTIALS")
    if not credentials:
        raise SystemExit("LP_CREDENTIALS environment variable missing")

    credentials = Credentials.from_string(credentials)
    return Launchpad(
        credentials, None, None, service_root="production", version="devel"
    )


def get_source_build_recipe(project_name: str, recipe_name: str):
    lp = get_launchpad_client()
    try:
        project = lp.projects[project_name]
    except KeyError:
        raise SystemExit(f"{project_name} was not found in Launchpad.")

    if project.recipes.total_size == 0:
        raise SystemExit(f"{project_name} does not have any recipes.")

    build_recipe = (
        recipe for recipe in project.recipes if recipe.name == recipe_name
    )
    # Note: this is intentionally an iterator because every call that we make
    #       to .name will make a GET request to LP, so we avoid the full
    #       unwrapping of the iterator given that we only ever going to use 1
    try:
        return next(build_recipe)
    except StopIteration:
        # There is no recipe with that name
        all_recipe_names = ", ".join(recipe.name for recipe in project.recipes)
        raise SystemExit(
            f'{project} does not have a "{recipe_name}" recipe '
            f"(possible recipes: {all_recipe_names})"
        )

def get_date_utc_now():
    return datetime.datetime.now(tz=datetime.timezone.utc)
