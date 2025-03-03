import os
import textwrap
import unittest
from unittest.mock import patch, mock_open

import os_resource


class LsbResourceTests(unittest.TestCase):
    @patch.dict(os.environ, {"SNAP_NAME": "test"})
    def test_get_release_file_path_snap(self):
        path = os_resource.get_release_file_path()
        self.assertEqual(path, "/var/lib/snapd/hostfs/etc/os-release")

    def test_get_release_file_path_deb(self):
        path = os_resource.get_release_file_path()
        self.assertEqual(path, "/etc/os-release")

    def test_get_release_info(self):
        data = textwrap.dedent(
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
        with patch("os_resource.open", mock_open(read_data=data)) as _:
            os_release = os_resource.get_release_info("")
        expected = {
            "distributor_id": "Ubuntu",
            "description": "Ubuntu 24.04.2 LTS",
            "release": "24.04",
            "codename": "noble",
        }
        self.assertEqual(os_release, expected)
