"""
This module contains various shared utils function used in
multiple release scripts
"""
import os
import datetime

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad


def get_launchpad_client() -> Launchpad:
    credentials = os.getenv("LP_CREDENTIALS")
    if not credentials:
        raise SystemExit("LP_CREDENTIALS environment variable missing")

    credentials = Credentials.from_string(credentials)
    return Launchpad(
        credentials, None, None, service_root="production", version="devel"
    )


def get_build_recipe(project_name: str, recipe_name: str):
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
