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
