import unittest
from unittest.mock import patch, MagicMock

import lp_copy_packages


class TestLpCopyPackages(unittest.TestCase):
    @patch("lp_copy_packages.Credentials")
    @patch("lp_copy_packages.Launchpad")
    @patch("os.getenv")
    def test_get_launchpad_client_ok(
        self, getenv_mock, launchpad_mock, credentials_mock
    ):
        getenv_mock.return_value = "some credential"

        lp_client = lp_copy_packages.get_launchpad_client()

        # credentials are built from the env
        self.assertTrue(credentials_mock.from_string.called)
        self.assertEqual(lp_client, launchpad_mock())

    @patch("os.getenv")
    def test_get_launchpad_client_no_cred(self, getenv_mock):
        getenv_mock.return_value = None

        with self.assertRaises(SystemExit):
            lp_copy_packages.get_launchpad_client()


class TestMain(unittest.TestCase):
    @patch("lp_copy_packages.get_launchpad_client")
    def test_main(self, get_launchpad_client_mock):
        lp_client = get_launchpad_client_mock()

        checkbox_dev_user = MagicMock()
        lp_client.people = {"checkbox-dev": checkbox_dev_user}

        source = MagicMock()
        ppas = checkbox_dev_user.getPPAByName()
        ppas.getPublishedSource.return_value = [source] * 5

        lp_copy_packages.main(
            ["checkbox-dev", "beta", "checkbox-dev", "stable"]
        )

        self.assertEqual(ppas.copyPackage.call_count, 5)
