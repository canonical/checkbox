#!/usr/bin/env python3
"""Tests for the lxd_support.py module.

Copyright 2024 Canonical Ltd.

Written by:
  Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import subprocess
from unittest import TestCase
from unittest.mock import MagicMock, patch

from checkbox_support.helpers.retry import mock_retry
from checkbox_support.lxd_support import LXD, LXDVM


@mock_retry()
@patch("checkbox_support.lxd_support.logging")
class TestLXD(TestCase):
    """Test cases for LXD instance wrapper."""

    def test_template_none(self, logging_mock):
        lxd = LXD(template_url=None)
        self.assertIsNone(lxd.template)

    @patch("os.path.isfile", return_value=True)
    @patch(
        "checkbox_support.lxd_support.urlparse",
        return_value=MagicMock(path="ubuntu.com/template"),
    )
    def test_template_exists(self, urlparse_mock, isfile_mock, logging_mock):
        lxd = LXD(template_url="https://ubuntu.com/template")
        self.assertEqual(lxd.template, "/tmp/template")

    def test_release_arg(self, logging_mock):
        lxd = LXD(release="24.04")
        self.assertEqual(lxd.release, "24.04")

    @patch.object(LXD, "download_image")
    @patch("os.path.isfile", return_value=False)
    @patch(
        "checkbox_support.lxd_support.urlparse",
        return_value=MagicMock(path="ubuntu.com/template"),
    )
    def test_template_download(
        self, urlparse_mock, isfile_mock, download_image_mock, logging_mock
    ):
        lxd = LXD(template_url="https://ubuntu.com/template")
        self.assertEqual(lxd.template, "/tmp/template")

    def test_image_none(self, logging_mock):
        lxd = LXD(image_url=None)
        self.assertIsNone(lxd.image)

    @patch("os.path.isfile", return_value=True)
    @patch(
        "checkbox_support.lxd_support.urlparse",
        return_value=MagicMock(path="ubuntu.com/image"),
    )
    def test_image_exists(self, urlparse_mock, isfile_mock, logging_mock):
        lxd = LXD(image_url="https://ubuntu.com/image")
        self.assertEqual(lxd.image, "/tmp/image")

    @patch.object(LXD, "download_image")
    @patch("os.path.isfile", return_value=False)
    @patch(
        "checkbox_support.lxd_support.urlparse",
        return_value=MagicMock(path="ubuntu.com/image"),
    )
    def test_image_download(
        self, urlparse_mock, isfile_mock, download_image_mock, logging_mock
    ):
        lxd = LXD(image_url="https://ubuntu.com/image")
        self.assertEqual(lxd.image, "/tmp/image")

    @patch(
        "subprocess.check_output",
        return_value=MagicMock(returncode=0, stdout="success", stderr=""),
    )
    def test_run_success(self, run_mock, logging_mock):
        self_mock = MagicMock()
        LXD.run(self_mock, "ip a")
        run_mock.assert_called_with(
            ["ip", "a"],
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
        )

    @patch(
        "subprocess.check_output",
        return_value=MagicMock(returncode=0, stdout="success", stderr=""),
    )
    def test_run_on_guest_success(self, run_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        LXD.run(self_mock, "ip a", on_guest=True)
        run_mock.assert_called_with(
            ["lxc", "exec", "testbed", "--", "ip", "a"],
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
        )

    @patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "", "fail"),
    )
    def test_run_fail(self, run_mock, logging_mock):
        self_mock = MagicMock()
        with self.assertRaises(subprocess.CalledProcessError):
            LXD.run(self_mock, "ip a")

    @patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "", "fail"),
    )
    def test_run_ignore_errors(self, run_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        LXD.run(self_mock, "ip a", ignore_errors=True)
        run_mock.assert_called_with(
            ["ip", "a"],
            stdout=subprocess.PIPE,
            timeout=None,
            check=True,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
        )

    @patch("urllib.request.urlretrieve")
    @patch("os.path.isfile", return_value=True)
    def test_download_image_exists(
        self, isfile_mock, urlretrieve_mock, logging_mock
    ):
        self_mock = MagicMock()
        LXD.download_image(self_mock, "https://ubuntu.com/image", "/tmp/image")
        self.assertEqual(isfile_mock.call_count, 1)
        self.assertFalse(urlretrieve_mock.called)

    @patch("os.path.isfile", side_effect=[False, True])
    @patch("urllib.request.urlretrieve")
    def test_download_image_success(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        LXD.download_image(self_mock, "https://ubuntu.com/image", "/tmp/image")
        self.assertEqual(isfile_mock.call_count, 2)
        self.assertTrue(urlretrieve_mock.called)

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve", side_effect=IOError)
    def test_download_image_http_error(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        with self.assertRaises(IOError):
            LXD.download_image(
                self_mock, "https://ubuntu.com/image", "/tmp/image"
            )
        self.assertEqual(isfile_mock.call_count, 1)
        self.assertTrue(urlretrieve_mock.called)

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve")
    def test_download_image_file_not_found(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        with self.assertRaises(FileNotFoundError):
            LXD.download_image(
                self_mock, "https://ubuntu.com/image", "/tmp/image"
            )
        self.assertEqual(isfile_mock.call_count, 2)
        self.assertTrue(urlretrieve_mock.called)

    def test_insert_images_local_success(self, logging_mock):
        self_mock = MagicMock(template="/tmp/template", image="/tmp/image")
        LXD.insert_images(self_mock)

    @patch("checkbox_support.lxd_support.run_with_retry")
    def test_insert_images_remote_success(
        self, logging_mock, run_with_retry_mock
    ):
        self_mock = MagicMock(template=None, image=None, remote="ubuntu:")
        LXD.insert_images(self_mock)

    @patch(
        "checkbox_support.lxd_support.run_with_retry",
        side_effect=subprocess.CalledProcessError(1, "", ""),
    )
    def test_insert_images_remote_fail(
        self, logging_mock, fake_run_with_retry_mock
    ):
        self_mock = MagicMock(template=None, image=None, remote="ubuntu:")
        with self.assertRaises(subprocess.CalledProcessError):
            LXD.insert_images(self_mock)

    def test_init_lxd_already_running(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run.return_value = MagicMock(returncode=0)
        LXD.init_lxd(self_mock)
        self.assertEqual(self_mock.run.call_count, 1)

    def test_init_lxd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run.side_effect = [
            subprocess.CalledProcessError(1, "", "lxd not running"),
            MagicMock(returncode=0),
        ]
        LXD.init_lxd(self_mock)
        self.assertEqual(self_mock.run.call_count, 2)
        self.assertTrue(self_mock.insert_images.called)

    def test_cleanup_success(self, logging_mock):
        self_mock = MagicMock()
        LXD.cleanup(self_mock)

    def test_launch_no_options(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        self_mock.image_alias = MagicMock(
            hex="656382d4-d820-4d01-944b-82b5b63041a7"
        )
        LXD.launch(self_mock)

    def test_launch_options(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        self_mock.image_alias = MagicMock(
            hex="656382d4-d820-4d01-944b-82b5b63041a7"
        )
        LXD.launch(self_mock, ["-d root,size=50GB"])
        self_mock.run.assert_called_with(
            "lxc launch 656382d4-d820-4d01-944b-82b5b63041a7 testbed -d root,size=50GB"
        )

    def test_stop_no_force(self, logging_mock):
        self_mock = MagicMock()
        LXD.stop(self_mock)

    def test_stop_force(self, logging_mock):
        self_mock = MagicMock()
        LXD.stop(self_mock, force=True)

    def test_start(self, logging_mock):
        self_mock = MagicMock()
        LXD.start(self_mock)

    def test_restart(self, logging_mock):
        self_mock = MagicMock()
        LXD.restart(self_mock)

    def test_add_device_no_options(self, logging_mock):
        self_mock = MagicMock()
        LXD.add_device(self_mock, "gpu", "gpu")

    def test_add_device_options(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        LXD.add_device(self_mock, "gpu", "gpu", ["pci=0000:0a:00.0"])
        self_mock.run.assert_called_with(
            "lxc config device add testbed gpu gpu pci=0000:0a:00.0"
        )

    def test_wait_until_running(self, logging_mock):
        self_mock = MagicMock()
        LXD.wait_until_running(self_mock)

    @patch.object(LXD, "cleanup")
    @patch.object(LXD, "init_lxd")
    def test_context_manager(self, init_lxd_mock, cleanup_mock, logging_mock):
        with LXD() as _:
            pass
        self.assertTrue(init_lxd_mock.called)
        self.assertTrue(cleanup_mock.called)


@mock_retry()
@patch("checkbox_support.lxd_support.logging")
class TestLXDVM(TestCase):
    """Test cases for LXD VM instance wrapper."""

    def test_insert_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = "/tmp/template"
        self_mock.image = "/tmp/image"
        LXDVM.insert_images(self_mock)

    def test_insert_images_no_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = None
        self_mock.image = None
        LXDVM.insert_images(self_mock)

    def test_launch_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        self_mock.template = "/tmp/template"
        self_mock.image = "/tmp/image"
        self_mock.image_alias = MagicMock(
            hex="656382d4-d820-4d01-944b-82b5b63041a7"
        )
        LXDVM.launch(self_mock)

    def test_launch_no_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        self_mock.remote = "ubuntu:"
        self_mock.template = None
        self_mock.image = None
        self_mock.image_alias = MagicMock(
            hex="656382d4-d820-4d01-944b-82b5b63041a7"
        )
        LXDVM.launch(self_mock)

    def test_launch_options(self, logging_mock):
        self_mock = MagicMock()
        self_mock.name = "testbed"
        self_mock.remote = "ubuntu:"
        self_mock.template = None
        self_mock.image = None
        self_mock.image_alias = MagicMock(
            hex="656382d4-d820-4d01-944b-82b5b63041a7"
        )
        LXDVM.launch(self_mock, options=["-d root,size=50GB"])

    @patch("checkbox_support.lxd_support.super")
    def test_add_device(self, super_mock, logging_mock):
        self_mock = MagicMock()
        LXDVM.add_device(self_mock, "gpu", "gpu")
