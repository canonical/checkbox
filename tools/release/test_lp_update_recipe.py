import unittest

from unittest.mock import MagicMock, patch

import lp_update_recipe


class TestUpdateBuildRecipe(unittest.TestCase):
    def test_get_build_path_provider(self):
        provider_recipe_name = "checkbox-provider-name-risk"
        self.assertEqual(
            lp_update_recipe.get_build_path(provider_recipe_name),
            "providers/name",
        )
        contrib_recipe_name = "checkbox-contrib-name-risk"
        self.assertEqual(
            lp_update_recipe.get_build_path(contrib_recipe_name),
            "contrib/name",
        )

    def test_get_build_path_checkbox_ng(self):
        checkbox_ng_recipe_name = "checkbox-ng-risk"
        self.assertEqual(
            lp_update_recipe.get_build_path(checkbox_ng_recipe_name),
            "checkbox-ng",
        )

    def test_get_updated_build_recipe(self):
        new_recipe = lp_update_recipe.get_updated_build_recipe(
            "checkbox-provider-base-edge", "X.Y.Z~dev13", "aaabbb"
        )
        # part path is correctly calculated
        self.assertIn("providers/base", new_recipe)
        # version is included in the recipe
        self.assertIn("X.Y.Z~dev13", new_recipe)
        # revision is also included in the recipe
        self.assertIn("aaabbb", new_recipe)

    @patch("lp_update_recipe.get_source_build_recipe")
    @patch("lp_update_recipe.print")
    @patch(
        "lp_update_recipe.get_active_series",
        new=MagicMock(return_value="noble"),
    )
    def test_main(self, print_mock, get_build_path_mock):
        lp_recipe = get_build_path_mock()

        lp_update_recipe.main(
            [
                "checkbox",
                "--recipe",
                "checkbox-support-edge",
                "--new-version",
                "X.Y.Z~dev2",
                "--revision",
                "abcd",
            ]
        )
        self.assertIn("X.Y.Z~dev2", lp_recipe.recipe_text)
        self.assertIn("checkbox-support", lp_recipe.recipe_text)
        self.assertIn("abcd", lp_recipe.recipe_text)
        self.assertTrue(lp_recipe.lp_save.called)

    @patch("lp_update_recipe.print")
    @patch("lp_update_recipe.get_launchpad_client")
    def test_get_active_series(self, get_launchpad_client_mock, print_mock):
        lp_mock = get_launchpad_client_mock()
        # if this broke, 10+yrs went by and this is still in use. Good :)
        # Update the following line with the latest LTS name
        active_release_mock = MagicMock(active=True)
        active_release_mock.name = "noble"
        active_undesired_mock = MagicMock(active=True)
        active_undesired_mock.name = " <this release is undesired> "
        lp_mock.projects["ubuntu"].series = [
            active_release_mock,
            active_undesired_mock,
        ]
        returned = lp_update_recipe.get_active_series()
        self.assertTrue(any(active_release_mock.name in x for x in returned))
        log = "\n".join(str(x) for x in print_mock.call_args_list)
        # active but undesired was reported
        self.assertIn(active_undesired_mock.name, log)
        # this assumes more than 1 distro is active, if this fails you are
        # desiring only 1 distro which is the latest lts from before
        self.assertIn("outdated", log)
