import textwrap
from unittest import TestCase
from unittest.mock import mock_open, patch

from checkbox_ng.support.snap_utils.system import (
    add_hostfs_prefix,
    get_series,
    in_strict_snap,
    on_ubuntucore,
)

UC24_OS_RELEASE = textwrap.dedent("""
    NAME="Ubuntu Core"
    VERSION="24"
    ID=ubuntu-core
    PRETTY_NAME="Ubuntu Core 24"
    VERSION_ID="24"
    """)

CLASSIC_OS_RELEASE = textwrap.dedent("""
    PRETTY_NAME="Ubuntu 24.04.4 LTS"
    NAME="Ubuntu"
    VERSION_ID="24.04"
    VERSION_CODENAME=noble
    ID=ubuntu
    """)

RELEASE_CONTENT = (
    "checkbox_ng.support.snap_utils.system.get_release_file_content"
)
RELEASE_INFO = "checkbox_ng.support.snap_utils.system.get_release_info"


class OnUbuntuCoreTests(TestCase):
    @patch(RELEASE_CONTENT, return_value=UC24_OS_RELEASE)
    def test_on_ubuntucore(self, _):
        self.assertTrue(on_ubuntucore())

    @patch(RELEASE_CONTENT, return_value=CLASSIC_OS_RELEASE)
    def test_on_classic(self, _):
        self.assertFalse(on_ubuntucore())

    @patch(RELEASE_CONTENT, side_effect=PermissionError)
    def test_inaccessible_host_release(self, _):
        with self.assertRaises(PermissionError):
            on_ubuntucore()


class GetSeriesTests(TestCase):
    @patch(RELEASE_INFO, return_value={"release": "24"})
    def test_ubuntucore(self, _):
        self.assertEqual(get_series(), "24")

    @patch(RELEASE_INFO, return_value={"release": "24.04"})
    def test_classic(self, _):
        self.assertEqual(get_series(), "24.04")

    @patch(RELEASE_INFO, side_effect=PermissionError)
    def test_inaccessible_host_release(self, _):
        with self.assertRaises(PermissionError):
            get_series()


class InStrictSnapTests(TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_not_a_snap(self):
        self.assertFalse(in_strict_snap())

    @patch.dict("os.environ", {"SNAP": "/snap/checkbox24/1"}, clear=True)
    @patch("builtins.open", mock_open(read_data="confinement: strict\n"))
    def test_strict_snap(self):
        self.assertTrue(in_strict_snap())

    @patch.dict("os.environ", {"SNAP": "/snap/checkbox/1"}, clear=True)
    @patch("builtins.open", mock_open(read_data="confinement: classic\n"))
    def test_classic_snap(self):
        self.assertFalse(in_strict_snap())


class AddHostfsPrefixTests(TestCase):
    @patch(
        "checkbox_ng.support.snap_utils.system.in_strict_snap",
        return_value=True,
    )
    def test_strict_snap(self, _):
        self.assertEqual(
            add_hostfs_prefix("/boot/grub"),
            "/var/lib/snapd/hostfs/boot/grub",
        )

    @patch(
        "checkbox_ng.support.snap_utils.system.in_strict_snap",
        return_value=False,
    )
    def test_not_strict_snap(self, _):
        self.assertEqual(add_hostfs_prefix("/boot/grub"), "/boot/grub")
