#!/usr/bin/env python3
"""Tests for the gpu_passthrough.py script.
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

import os
import subprocess
import urllib.error
from unittest import TestCase
from unittest.mock import MagicMock, patch

from gpu_passthrough import (
    LXD,
    LXDVM,
    add_apt_repo,
    build_gpu_test,
    main,
    parse_args,
    run_gpu_test,
    test_lxd_gpu,
    test_lxdvm_gpu,
)


@patch("gpu_passthrough.logging")
class TestLXD(TestCase):
    def test_template_none(self, logging_mock):
        lxd = LXD(template_url=None)
        self.assertIsNone(lxd.template)

    @patch("os.path.isfile", return_value=True)
    @patch(
        "gpu_passthrough.urlparse",
        return_value=MagicMock(path="ubuntu.com/template"),
    )
    def test_template_exists(self, urlparse_mock, isfile_mock, logging_mock):
        lxd = LXD(template_url="https://ubuntu.com/template")
        self.assertEqual(lxd.template, "/tmp/template")

    @patch.object(LXD, "download_image")
    @patch("os.path.isfile", return_value=False)
    @patch(
        "gpu_passthrough.urlparse",
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
        "gpu_passthrough.urlparse",
        return_value=MagicMock(path="ubuntu.com/image"),
    )
    def test_image_exists(self, urlparse_mock, isfile_mock, logging_mock):
        lxd = LXD(image_url="https://ubuntu.com/image")
        self.assertEqual(lxd.image, "/tmp/image")

    @patch.object(LXD, "download_image")
    @patch("os.path.isfile", return_value=False)
    @patch(
        "gpu_passthrough.urlparse",
        return_value=MagicMock(path="ubuntu.com/image"),
    )
    def test_image_download(
        self, urlparse_mock, isfile_mock, download_image_mock, logging_mock
    ):
        lxd = LXD(image_url="https://ubuntu.com/image")
        self.assertEqual(lxd.image, "/tmp/image")

    @patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="success", stderr=""),
    )
    def test_run_success(self, run_mock, logging_mock):
        self_mock = MagicMock()
        try:
            LXD.run(self_mock, "ip a")
        except subprocess.CalledProcessError:
            self.fail("run raised CalledProcessError")

    @patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="success", stderr=""),
    )
    def test_run_on_guest_success(self, run_mock, logging_mock):
        self_mock = MagicMock()
        try:
            LXD.run(self_mock, "ip a", on_guest=True)
        except subprocess.CalledProcessError:
            self.fail("run raised CalledProcessError")

    @patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="fail"),
    )
    def test_run_fail(self, run_mock, logging_mock):
        run_mock().check_returncode.side_effect = [
            subprocess.CalledProcessError(
                run_mock.returncode, "ip a", run_mock.stdout, run_mock.stderr
            )
        ]
        self_mock = MagicMock()
        with self.assertRaises(subprocess.CalledProcessError):
            LXD.run(self_mock, "ip a", check=True)

    @patch("os.path.isfile", return_value=True)
    @patch("urllib.request.urlretrieve")
    def test_download_image_success(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        try:
            LXD.download_image(
                self_mock, "https://ubuntu.com/image", "/tmp/image"
            )
        except FileNotFoundError:
            self.fail("download_image raised FileNotFoundError")

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve", side_effect=IOError)
    def test_download_image_http_error(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        with self.assertRaises(FileNotFoundError):
            LXD.download_image(
                self_mock, "https://ubuntu.com/image", "/tmp/image"
            )

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve", side_effect=ValueError)
    def test_download_image_val_error(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()
        with self.assertRaises(FileNotFoundError):
            LXD.download_image(
                self_mock, "https://ubuntu.com/image", "/tmp/image"
            )

    def test_insert_images_local_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = "/tmp/template"
        self_mock.image = "/tmp/image"
        LXD.insert_images(self_mock)

    def test_insert_images_remote_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = None
        self_mock.image = None
        self_mock.remote = "ubuntu:"
        self_mock.run.return_value = MagicMock(returncode=0)
        try:
            LXD.insert_images(self_mock)
        except RuntimeError:
            self.fail("insert_images raised RuntimeError")

    def test_insert_images_remote_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = None
        self_mock.image = None
        self_mock.remote = "ubuntu:"
        self_mock.run.return_value = MagicMock(returncode=1)
        with self.assertRaises(RuntimeError):
            LXD.insert_images(self_mock)

    def test_init_lxd_already_running(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run.return_value = MagicMock(returncode=0)
        LXD.init_lxd(self_mock)
        self.assertEqual(self_mock.run.call_count, 1)

    def test_init_lxd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run.side_effect = [
            MagicMock(returncode=1),
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
        LXD.launch(self_mock)

    def test_launch_options(self, logging_mock):
        self_mock = MagicMock()
        LXD.launch(self_mock, ["-d root,size=50GB"])

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
        LXD.add_device(self_mock, "gpu", "gpu", ["pci=0000:0a:00.0"])


@patch("gpu_passthrough.logging")
class TestLXDVM(TestCase):
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
        self_mock.template = "/tmp/template"
        self_mock.image = "/tmp/image"
        LXDVM.launch(self_mock)

    def test_launch_no_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = None
        self_mock.image = None
        LXDVM.launch(self_mock)

    def test_launch_options(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template = None
        self_mock.image = None
        LXDVM.launch(self_mock, options=["-d root,size=50GB"])

    @patch("gpu_passthrough.super")
    def test_add_device(self, super_mock, logging_mock):
        self_mock = MagicMock()
        LXDVM.add_device(self_mock, "gpu", "gpu")


@patch("gpu_passthrough.logging")
class TestMain(TestCase):
    def test_add_apt_repo_no_pinfile(self, logging_mock):
        instance = MagicMock()
        repo = MagicMock(pinfile=None)
        add_apt_repo(instance, repo)

    def test_add_apt_repo_download_pinfile(self, logging_mock):
        instance = MagicMock()
        repo = MagicMock(pinfile="https://ubuntu.com/pinfile")
        add_apt_repo(instance, repo)

    def test_add_apt_repo_text_pinfile(self, logging_mock):
        instance = MagicMock()
        repo = MagicMock(pinfile="Package: *\nPin: ...")
        add_apt_repo(instance, repo)

    def test_build_gpu_test(self, logging_mock):
        instance = MagicMock()
        build_gpu_test(instance, "nvidia")

    @patch("time.time", side_effect=[0, 1])
    def test_run_gpu_test_success(self, time_mock, logging_mock):
        instance = MagicMock()
        try:
            run_gpu_test(instance, run_count=1, threshold_sec=2)
        except SystemExit:
            self.fail("run_gpu_test raised SystemExit")

    @patch("time.time", side_effect=[0, 2])
    def test_run_gpu_test_failure(self, time_mock, logging_mock):
        instance = MagicMock()
        with self.assertRaises(SystemExit):
            run_gpu_test(instance, run_count=1, threshold_sec=1)

    @patch("gpu_passthrough.run_gpu_test")
    @patch("gpu_passthrough.build_gpu_test")
    @patch("time.sleep")
    @patch("gpu_passthrough.LXD")
    def test_test_lxd_gpu(
        self, lxd_mock, sleep_mock, build_mock, run_mock, logging_mock
    ):
        args = MagicMock(vendor="nvidia")
        test_lxd_gpu(args)

    @patch("gpu_passthrough.run_gpu_test")
    @patch("gpu_passthrough.build_gpu_test")
    @patch("time.sleep")
    @patch("gpu_passthrough.LXDVM")
    def test_test_lxdvm_gpu(
        self, lxdvm_mock, sleep_mock, build_mock, run_mock, logging_mock
    ):
        args = MagicMock(vendor="nvidia")
        test_lxdvm_gpu(args)

    @patch("gpu_passthrough.argparse")
    def test_parse_args(self, argparse_mock, logging_mock):
        parse_args()

    @patch("gpu_passthrough.parse_args")
    def test_main(self, parse_args_mock, logging_mock):
        main()
