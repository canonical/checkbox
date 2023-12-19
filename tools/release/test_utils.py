import unittest

from unittest.mock import patch

import utils


class TestUtils(unittest.TestCase):
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
        self.assertEqual(lp_client, launchpad_mock())

    @patch("os.getenv")
    def test_get_launchpad_client_no_cred(self, getenv_mock):
        getenv_mock.return_value = None

        with self.assertRaises(SystemExit):
            utils.get_launchpad_client()
