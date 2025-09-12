import textwrap
import unittest
from unittest.mock import patch, mock_open, MagicMock

from checkbox_support.helpers.release_info import (
    get_release_info,
    get_release_file_content,
)


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
            "checkbox_support.helpers.release_info.open",
            mock_open(read_data=self.os_release_data),
        ):
            os_release_data = get_release_file_content()
        self.assertIn("UBUNTU_CODENAME=noble\n", os_release_data)

    def test_get_release_file_content_classic(self):
        open_mock = MagicMock()
        with open_mock() as f:
            f.read.side_effect = [
                FileNotFoundError("first"),
                self.os_release_data,
            ]
        with patch("checkbox_support.helpers.release_info.open", open_mock):
            os_release_data = get_release_file_content()
        self.assertIn("UBUNTU_CODENAME=noble\n", os_release_data)

    @patch("checkbox_support.helpers.release_info.get_release_file_content")
    def test_get_release_info(self, mock_file_content):
        mock_file_content.return_value = self.os_release_data
        os_release = get_release_info()
        expected = {
            "distributor_id": "Ubuntu",
            "description": "Ubuntu 24.04.2 LTS",
            "release": "24.04",
            "codename": "noble",
        }
        self.assertEqual(os_release, expected)

    @patch("checkbox_support.helpers.release_info.get_release_file_content")
    def test_get_release_info_empty_lines(self, mock_file_content):
        os_release_data = textwrap.dedent(
            """
        PRETTY_NAME="Ubuntu 22.04.5 LTS"

        NAME="Ubuntu"
        VERSION_ID="22.04"

        VERSION_CODENAME=jammy
        """
        ).strip()
        mock_file_content.return_value = os_release_data
        os_release = get_release_info()
        expected = {
            "distributor_id": "Ubuntu",
            "description": "Ubuntu 22.04.5 LTS",
            "release": "22.04",
            "codename": "jammy",
        }
        self.assertEqual(os_release, expected)

    @patch("checkbox_support.helpers.release_info.get_release_file_content")
    def test_get_release_info_core_no_codename(self, mock_file_content):
        # core doesn't have codename
        os_release_data = textwrap.dedent(
            """
            NAME="Ubuntu Core"
            VERSION="22"
            ID=ubuntu-core
            PRETTY_NAME="Ubuntu Core 22"
            VERSION_ID="22"
            HOME_URL="https://snapcraft.io/"
            BUG_REPORT_URL="https://bugs.launchpad.net/snappy/
            """
        ).strip()

        mock_file_content.return_value = os_release_data
        os_release = get_release_info()
        expected = {
            "distributor_id": "Ubuntu Core",
            "description": "Ubuntu Core 22",
            "release": "22",
            "codename": "Ubuntu Core 22",
        }
        self.assertEqual(os_release, expected)
