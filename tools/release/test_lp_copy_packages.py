import unittest
from unittest.mock import patch, MagicMock

import lp_copy_packages


class TestMain(unittest.TestCase):
    @patch("lp_copy_packages.get_launchpad_client")
    def test_main(self, get_launchpad_client_mock):
        lp_client = get_launchpad_client_mock()

        checkbox_dev_user = MagicMock()
        lp_client.people = {"checkbox-dev": checkbox_dev_user}

        source_to_copy = MagicMock(date_superseded=None)
        source_no_copy_superseeded = MagicMock(date_superseded="some date")
        source_no_copy_outdated_distro = MagicMock(date_superseded=None)

        ppas = checkbox_dev_user.getPPAByName()
        ppas.getPublishedSources.return_value = [source_to_copy] * 5 + [
            source_no_copy_superseeded,
            source_no_copy_outdated_distro,
        ]

        lp_copy_packages.main(
            ["checkbox-dev", "beta", "checkbox-dev", "stable"]
        )

        self.assertEqual(ppas.copyPackage.call_count, 5)
