import unittest

from unittest.mock import MagicMock, patch

import utils


class TestUtils(unittest.TestCase):
    @patch("utils.get_launchpad_client")
    def test_get_source_build_recipe_timeout(self, client_mock):
        recipe = MagicMock()
        recipe.name = "checkbox-ng-edge"
        project = client_mock.return_value.projects.__getitem__.return_value
        project.recipes = MagicMock()
        project.recipes.total_size = 1
        project.recipes.__iter__.return_value = iter([recipe])

        result = utils.get_source_build_recipe(
            "checkbox", "checkbox-ng-edge", timeout=30
        )

        client_mock.assert_called_once_with(timeout=30)
        self.assertIs(result, recipe)

    @patch("utils.get_launchpad_client")
    def test_get_source_build_recipe_default_timeout(self, client_mock):
        recipe = MagicMock()
        recipe.name = "checkbox-ng-edge"
        project = client_mock.return_value.projects.__getitem__.return_value
        project.recipes = MagicMock()
        project.recipes.total_size = 1
        project.recipes.__iter__.return_value = iter([recipe])

        result = utils.get_source_build_recipe("checkbox", "checkbox-ng-edge")

        client_mock.assert_called_once_with(timeout=None)
        self.assertIs(result, recipe)

    @patch("utils.Credentials")
    @patch("utils.Launchpad")
    @patch("os.getenv")
    def test_get_launchpad_client_ok(
        self, getenv_mock, launchpad_mock, credentials_mock
    ):
        getenv_mock.return_value = "some credential"

        lp_client = utils.get_launchpad_client()

        # credentials are built from the env
        self.assertTrue(credentials_mock.from_string.called)
        launchpad_mock.assert_called_once_with(
            credentials_mock.from_string.return_value,
            None,
            None,
            service_root="production",
            version="devel",
            timeout=None,
        )
        self.assertEqual(lp_client, launchpad_mock.return_value)

    @patch("utils.Credentials")
    @patch("utils.Launchpad")
    @patch("os.getenv", return_value="some credential")
    def test_get_launchpad_client_timeout(
        self, getenv_mock, launchpad_mock, credentials_mock
    ):
        lp_client = utils.get_launchpad_client(timeout=30)

        launchpad_mock.assert_called_once_with(
            credentials_mock.from_string.return_value,
            None,
            None,
            service_root="production",
            version="devel",
            timeout=30,
        )
        self.assertEqual(lp_client, launchpad_mock.return_value)

    @patch("os.getenv")
    def test_get_launchpad_client_no_cred(self, getenv_mock):
        getenv_mock.return_value = None

        with self.assertRaises(SystemExit):
            utils.get_launchpad_client()
