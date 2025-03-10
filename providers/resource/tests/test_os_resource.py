import os
import textwrap
import unittest
from unittest.mock import patch, mock_open, MagicMock

import os_resource


class OsResourceTests(unittest.TestCase):
    os_release_data = textwrap.dedent(
        """
        PRETTY_NAME="Ubuntu 24.04.2 LTS"
        NAME="Ubuntu"
        VERSION_ID="24.04"
        VERSION="24.04.2 LTS (Noble Numbat)"
        VERSION_CODENAME=noble
        ID=ubuntu
        ID_LIKE=debian
        HOME_URL="https://www.ubuntu.com/"
        SUPPORT_URL="https://help.ubuntu.com/"
        BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
        PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
        UBUNTU_CODENAME=noble
        LOGO=ubuntu-logo
        """
    ).strip()

    def test_get_release_file_content(self):
        with patch(
            "os_resource.open", mock_open(read_data=self.os_release_data)
        ):
            os_release_data = os_resource.get_release_file_content()
        self.assertIn("UBUNTU_CODENAME=noble\n", os_release_data)

    def test_get_release_file_content_classic(self):
        open_mock = MagicMock()
        with open_mock() as f:
            f.read.side_effect = [
                FileNotFoundError("first"),
                self.os_release_data,
            ]
        with patch("os_resource.open", open_mock):
            os_release_data = os_resource.get_release_file_content()
        self.assertIn("UBUNTU_CODENAME=noble\n", os_release_data)

    def test_get_release_info(self):
        os_release = os_resource.get_release_info(self.os_release_data)
        expected = {
            "distributor_id": "Ubuntu",
            "description": "Ubuntu 24.04.2 LTS",
            "release": "24.04",
            "codename": "noble",
        }
        self.assertEqual(os_release, expected)

    def test_get_release_info_empty_lines(self):
        os_release_data = textwrap.dedent(
            """
        PRETTY_NAME="Ubuntu 22.04.5 LTS"

        NAME="Ubuntu"
        VERSION_ID="22.04"

        VERSION_CODENAME=jammy
        """
        ).strip()
        os_release = os_resource.get_release_info(os_release_data)
        expected = {
            "distributor_id": "Ubuntu",
            "description": "Ubuntu 22.04.5 LTS",
            "release": "22.04",
            "codename": "jammy",
        }
        self.assertEqual(os_release, expected)
