import unittest
from unittest.mock import patch, MagicMock

import lp_copy_packages


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
