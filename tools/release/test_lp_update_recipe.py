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
