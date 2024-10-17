#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#   Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import urllib.error
from unittest import TestCase
from unittest.mock import MagicMock, patch

from virtualization import (
    KVMTest,
    LXDTest,
    LXDTest_vm,
    RunCommand,
    test_kvm,
    test_lxd,
    test_lxd_vgpu,
    test_lxd_vm,
    test_lxd_vm_vgpu,
)


class TestRunCommand(TestCase):
    @patch(
        "virtualization.Popen",
        return_value=MagicMock(
            returncode=0, communicate=MagicMock(return_value=("out", "err"))
        ),
    )
    def test_run(self, popen_mock):
        task = RunCommand("ls")
        self.assertTrue(popen_mock.called)
        self.assertEqual(task.cmd, "ls")
        self.assertEqual(task.returncode, 0)
        self.assertEqual(task.stdout, "out")
        self.assertEqual(task.stderr, "err")


@patch("virtualization.logging")
class TestLXDTest(TestCase):
    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(
            returncode=0, cmd="ls", stdout="out", stderr="err"
        ),
    )
    def test_run_command_success(self, run_command_mock, logging_mock):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls")
        self.assertTrue(ret)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(returncode=0, cmd="ls", stdout="", stderr=""),
    )
    def test_run_command_success_no_out(self, run_command_mock, logging_mock):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls")
        self.assertTrue(ret)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(
            returncode=0, cmd="ls", stdout="out", stderr="err"
        ),
    )
    def test_run_command_success_no_log_stderr(
        self, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls", log_stderr=False)
        self.assertTrue(ret)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(
            returncode=0, cmd="ls", stdout="out", stderr="err"
        ),
    )
    def test_run_command_on_guest_success(
        self, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls", on_guest=True)
        self.assertTrue(ret)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(
            returncode=1, cmd="ls", stdout="out", stderr="err"
        ),
    )
    def test_run_command_failure(self, run_command_mock, logging_mock):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls")
        self.assertFalse(ret)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(
            returncode=1, cmd="ls", stdout="out", stderr="err"
        ),
    )
    def test_run_command_failure_no_log_stderr(
        self, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.run_command(self_mock, "ls", log_stderr=False)
        self.assertFalse(ret)

    def test_init_lxd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, True]

        ret = LXDTest.init_lxd(self_mock)
        self.assertTrue(ret)
        self.assertEqual(self_mock.run_command.call_count, 2)

    def test_init_lxd_already_started(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True]

        ret = LXDTest.init_lxd(self_mock)
        self.assertTrue(ret)
        self.assertEqual(self_mock.run_command.call_count, 1)

    def test_init_lxd_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, False]

        ret = LXDTest.init_lxd(self_mock)
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 2)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_template_success(self, isfile_mock, logging_mock):
        self_mock = MagicMock(template_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = "/tmp/file"

        ret = LXDTest.retrieve_template(self_mock)
        self.assertTrue(ret)
        self.assertTrue(isfile_mock.called)
        self.assertTrue(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=True)
    def test_retrieve_template_already_exists(self, isfile_mock, logging_mock):
        self_mock = MagicMock(template_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = "/tmp/file"

        ret = LXDTest.retrieve_template(self_mock)
        self.assertTrue(ret)
        self.assertTrue(isfile_mock.called)
        self.assertFalse(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_template_none(self, isfile_mock, logging_mock):
        self_mock = MagicMock(template_url=None)
        self_mock.download_images.return_value = False

        ret = LXDTest.retrieve_template(self_mock)
        self.assertTrue(ret)
        self.assertFalse(isfile_mock.called)
        self.assertFalse(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_template_failure(self, isfile_mock, logging_mock):
        self_mock = MagicMock(template_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = False

        ret = LXDTest.retrieve_template(self_mock)
        self.assertFalse(ret)
        self.assertTrue(isfile_mock.called)
        self.assertTrue(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_image_success(self, isfile_mock, logging_mock):
        self_mock = MagicMock(image_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = "/tmp/file"

        ret = LXDTest.retrieve_image(self_mock)
        self.assertTrue(ret)
        self.assertTrue(isfile_mock.called)
        self.assertTrue(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=True)
    def test_retrieve_image_already_exists(self, isfile_mock, logging_mock):
        self_mock = MagicMock(image_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = False

        ret = LXDTest.retrieve_image(self_mock)
        self.assertTrue(ret)
        self.assertTrue(isfile_mock.called)
        self.assertFalse(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_image_failure(self, isfile_mock, logging_mock):
        self_mock = MagicMock(image_url="https://ubuntu.com/file")
        self_mock.download_images.return_value = False

        ret = LXDTest.retrieve_image(self_mock)
        self.assertFalse(ret)
        self.assertTrue(isfile_mock.called)
        self.assertTrue(self_mock.download_images.called)

    @patch("os.path.isfile", return_value=False)
    def test_retrieve_image_none(self, isfile_mock, logging_mock):
        self_mock = MagicMock(image_url=None)
        self_mock.download_images.return_value = False

        ret = LXDTest.retrieve_image(self_mock)
        self.assertTrue(ret)
        self.assertFalse(isfile_mock.called)
        self.assertFalse(self_mock.download_images.called)

    def test_insert_images_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.run_command.return_value = True

        ret = LXDTest.insert_images(self_mock)
        self.assertTrue(ret)
        self.assertEqual(self_mock.run_command.call_count, 1)

    def test_insert_images_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.run_command.return_value = False

        ret = LXDTest.insert_images(self_mock)
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 1)

    def test_insert_images_import_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None
        self_mock.run_command.return_value = True

        ret = LXDTest.insert_images(self_mock)
        self.assertTrue(ret)
        self.assertEqual(self_mock.run_command.call_count, 1)

    def test_insert_images_import_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None
        self_mock.run_command.return_value = False

        ret = LXDTest.insert_images(self_mock)
        self.assertFalse(ret)

    def test_setup_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = True

        ret = LXDTest.setup(self_mock)
        self.assertTrue(ret)

    def test_setup_fail_init_lxd(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = False
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = True

        ret = LXDTest.setup(self_mock)
        self.assertFalse(ret)

    def test_setup_fail_retrieve_template(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = False
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = True

        ret = LXDTest.setup(self_mock)
        self.assertFalse(ret)

    def test_setup_fail_insert_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = False

        ret = LXDTest.setup(self_mock)
        self.assertFalse(ret)

    def test_add_gpu_device_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.add_gpu_device(
            self_mock, gpu_vendor="nvidia", gpu_pci="0000:57:00.0"
        )
        self.assertTrue(ret)

    def test_add_gpu_device_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        ret = LXDTest.add_gpu_device(self_mock, gpu_vendor="amd")
        self.assertFalse(ret)

    def test_configure_gpu_device_nvidia_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.configure_gpu_device(self_mock, gpu_vendor="nvidia")
        self.assertTrue(ret)

    def test_configure_gpu_device_nvidia_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        ret = LXDTest.configure_gpu_device(self_mock, gpu_vendor="nvidia")
        self.assertFalse(ret)

    def test_configure_gpu_device_amd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.configure_gpu_device(self_mock, gpu_vendor="amd")
        self.assertTrue(ret)

    def test_configure_gpu_device_amd_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        ret = LXDTest.configure_gpu_device(self_mock, gpu_vendor="amd")
        self.assertFalse(ret)

    def test_configure_gpu_device_unrecognized_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        ret = LXDTest.configure_gpu_device(self_mock, gpu_vendor="fake_vendor")
        self.assertFalse(ret)

    def test_add_apt_repo_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint"
        )
        self.assertTrue(ret)

    def test_add_apt_repo_web_pinfile(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.add_apt_repo(
            self_mock,
            "repo",
            "line",
            "gpg",
            "finerprint",
            "https://ubuntu.com/file",
        )
        self.assertTrue(ret)

    def test_add_apt_repo_text_pinfile(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint", "pinfile contents"
        )
        self.assertTrue(ret)

    def test_add_apt_repo_gpg_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, True, True]

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint"
        )
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 1)

    def test_add_apt_repo_pinfile_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False, True, True]

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint", "pinfile contents"
        )
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 2)

    def test_add_apt_repo_setup_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False, True]

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint"
        )
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 2)

    def test_add_apt_repo_update_cache_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, False]

        ret = LXDTest.add_apt_repo(
            self_mock, "repo", "line", "gpg", "finerprint"
        )
        self.assertFalse(ret)
        self.assertEqual(self_mock.run_command.call_count, 3)

    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(returncode=0, stdout="7.5"),
    )
    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    def test_build_vgpu_test_nvidia_success(
        self, uname_mock, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "nvidia")
        self.assertTrue(ret)

    @patch("virtualization.RunCommand", return_value=MagicMock(returncode=1))
    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    def test_build_vgpu_test_nvidia_fallback_arch_success(
        self, uname_mock, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "nvidia")
        self.assertTrue(ret)

    @patch("virtualization.RunCommand", return_value=MagicMock(returncode=1))
    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    def test_build_vgpu_test_nvidia_repo_failure(
        self, uname_mock, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = False
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("virtualization.RunCommand", return_value=MagicMock(returncode=1))
    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    def test_build_vgpu_test_nvidia_cuda_install_failure(
        self, uname_mock, run_command_mock, logging_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = False

        ret = LXDTest.build_vgpu_test(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_build_vgpu_test_amd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "amd")
        self.assertTrue(ret)

    def test_build_vgpu_test_amd_repo_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = False
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "amd")
        self.assertFalse(ret)

    def test_build_vgpu_test_amd_rocm_install_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = False

        ret = LXDTest.build_vgpu_test(self_mock, "amd")
        self.assertFalse(ret)

    def test_build_vgpu_test_unsupported_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_apt_repo.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.build_vgpu_test(self_mock, "fake_vendor")
        self.assertFalse(ret)

    @patch("os.path.isfile", return_value=True)
    @patch("urllib.request.urlretrieve")
    def test_download_images_success(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.download_images(self_mock, "https://ubuntu.com", "file")
        self.assertEqual(ret, "file")

    @patch("os.path.isfile", return_value=True)
    @patch("urllib.request.urlretrieve", side_effect=IOError)
    def test_download_images_download_failure(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.download_images(self_mock, "https://ubuntu.com", "file")
        self.assertFalse(ret)

    @patch("os.path.isfile", return_value=True)
    @patch("urllib.request.urlretrieve", side_effect=ValueError)
    def test_download_images_url_failure(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.download_images(self_mock, " bad_url", "file")
        self.assertFalse(ret)

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve")
    def test_download_images_cannot_find_file_failure(
        self, urlretrieve_mock, isfile_mock, logging_mock
    ):
        self_mock = MagicMock()

        ret = LXDTest.download_images(self_mock, " https://ubuntu.com", "file")
        self.assertFalse(ret)

    def test_cleanup_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_Command.return_value = True

        LXDTest.cleanup(self_mock)

    def test_launch_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.launch(self_mock)
        self.assertTrue(ret)

    def test_launch_setup_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = False
        self_mock.run_command.return_value = True

        ret = LXDTest.launch(self_mock)
        self.assertFalse(ret)

    def test_launch_launch_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.side_effect = [False, True]

        ret = LXDTest.launch(self_mock)
        self.assertFalse(ret)

    def test_launch_list_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.side_effect = [True, False]

        ret = LXDTest.launch(self_mock)
        self.assertFalse(ret)

    def test_test_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest.test(self_mock)
        self.assertTrue(ret)

    def test_test_launch_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False
        self_mock.run_command.return_value = True

        ret = LXDTest.test(self_mock)
        self.assertFalse(ret)

    def test_test_dd_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = False

        ret = LXDTest.test(self_mock)
        self.assertFalse(ret)

    @patch("time.time", side_effect=[0, 1])
    @patch("time.sleep")
    def test_test_vgpu_success(self, sleep_mock, time_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = True
        self_mock.run_command.return_value = True
        self_mock.build_vgpu_test.return_value = True

        ret = LXDTest.test_vgpu(
            self_mock, "nvidia", run_count=1, threshold_sec=2
        )
        self.assertTrue(ret)

    def test_test_vgpu_unrecognized_failure(self, logging_mock):
        self_mock = MagicMock()

        ret = LXDTest.test_vgpu(self_mock, "fake_vendor")
        self.assertFalse(ret)

    def test_test_vgpu_launch_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_test_vgpu_add_gpu_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = False

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("time.sleep")
    def test_test_vgpu_configure_failure(self, sleep_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = False

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("time.sleep")
    def test_test_vgpu_restart_failure(self, sleep_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = True
        self_mock.run_command.return_value = False

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("time.sleep")
    def test_test_vgpu_build_failure(self, sleep_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = True
        self_mock.run_command.return_value = True
        self_mock.build_vgpu_test.return_value = False

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("time.time", side_effect=[0, 2])
    @patch("time.sleep")
    def test_test_vgpu_test_failure(self, sleep_mock, time_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, False]
        self_mock.build_vgpu_test.return_value = True

        ret = LXDTest.test_vgpu(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("time.time", side_effect=[0, 2])
    @patch("time.sleep")
    def test_test_vgpu_result_failure(
        self, sleep_mock, time_mock, logging_mock
    ):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.add_gpu_device.return_value = True
        self_mock.configure_gpu_device.return_value = True
        self_mock.run_command.return_value = True
        self_mock.build_vgpu_test.return_value = True

        ret = LXDTest.test_vgpu(
            self_mock, "nvidia", run_count=1, threshold_sec=1
        )
        self.assertFalse(ret)


@patch("virtualization.logging")
class TestLXDTest_vm(TestCase):
    def test_insert_images_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "t.tar.gz"
        self_mock.image_tarball = "i.tar.gz"
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.insert_images(self_mock)
        self.assertTrue(ret)

    def test_insert_images_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "t.tar.gz"
        self_mock.image_tarball = "i.tar.gz"
        self_mock.run_command.return_value = False

        ret = LXDTest_vm.insert_images(self_mock)
        self.assertFalse(ret)

    def test_insert_images_none(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None

        ret = LXDTest_vm.insert_images(self_mock)
        self.assertTrue(ret)

    def test_launch_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "https://ubuntu.com/file"
        self_mock.template_url = "https://ubuntu.com/file"
        self_mock.launch_options = None
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.launch(self_mock)
        self.assertTrue(ret)

    def test_launch_setup_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = False

        ret = LXDTest_vm.launch(self_mock)
        self.assertFalse(ret)

    def test_launch_launching_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = None
        self_mock.template_url = None
        self_mock.launch_options = ["-d root,size=50GB"]
        self_mock.run_command.side_effect = [False, True, True]

        ret = LXDTest_vm.launch(self_mock)
        self.assertFalse(ret)

    def test_launch_start_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = None
        self_mock.template_url = None
        self_mock.launch_options = None
        self_mock.run_command.side_effect = [True, False, True]

        ret = LXDTest_vm.launch(self_mock)
        self.assertFalse(ret)

    def test_launch_listing_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = None
        self_mock.template_url = None
        self_mock.launch_options = None
        self_mock.run_command.side_effect = [True, True, False]

        ret = LXDTest_vm.launch(self_mock)
        self.assertFalse(ret)

    @patch("virtualization.super")
    def test_add_gpu_device_success(self, super_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True
        super_mock().add_gpu_device.return_value = True

        ret = LXDTest_vm.add_gpu_device(self_mock, "nvidia")
        self.assertTrue(ret)

    def test_add_gpu_device_stop_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, True]

        ret = LXDTest_vm.add_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("virtualization.super")
    def test_add_gpu_device_add_failure(self, super_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True
        super_mock().add_gpu_device.return_value = False

        ret = LXDTest_vm.add_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    @patch("virtualization.super")
    def test_add_gpu_device_start_failure(self, super_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False]
        super_mock().add_gpu_device.return_value = True

        ret = LXDTest_vm.add_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_configure_gpu_device_update_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        ret = LXDTest_vm.configure_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_configure_gpu_device_nvidia_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.configure_gpu_device(self_mock, "nvidia")
        self.assertTrue(ret)

    def test_configure_gpu_device_nvidia_tool_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False, True]

        ret = LXDTest_vm.configure_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_configure_gpu_device_nvidia_drivers_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, False]

        ret = LXDTest_vm.configure_gpu_device(self_mock, "nvidia")
        self.assertFalse(ret)

    def test_configure_gpu_device_amd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.configure_gpu_device(self_mock, "amd")
        self.assertTrue(ret)

    def test_configure_gpu_device_amd_update_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False, True, True]

        ret = LXDTest_vm.configure_gpu_device(self_mock, "amd")
        self.assertFalse(ret)

    def test_configure_gpu_device_amd_drivers_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, False, True]

        ret = LXDTest_vm.configure_gpu_device(self_mock, "amd")
        self.assertFalse(ret)

    def test_configure_gpu_device_amd_modules_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, True, False]

        ret = LXDTest_vm.configure_gpu_device(self_mock, "amd")
        self.assertFalse(ret)

    def test_configure_gpu_device_unrecognized_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.configure_gpu_device(self_mock, "fake_vendor")
        self.assertFalse(ret)

    @patch("time.sleep")
    def test_test_success(self, sleep_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = True

        ret = LXDTest_vm.test(self_mock)
        self.assertTrue(ret)

    def test_test_launch_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        ret = LXDTest_vm.test(self_mock)
        self.assertFalse(ret)

    @patch("time.sleep")
    def test_test_failure(self, sleep_mock, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = False

        ret = LXDTest_vm.test(self_mock)
        self.assertFalse(ret)


@patch("virtualization.print")
@patch("virtualization.logging")
class TestMain(TestCase):
    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vm_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, image=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(
        os.environ,
        {"LXD_TEMPLATE": "template", "KVM_IMAGE": "image"},
        clear=True,
    )
    def test_test_lxd_vm_environ_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, image=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vm_args_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template="template", image="image")

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test", return_value=False)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vm_failure(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, image=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm(args)
        self.assertEqual(cm.exception.code, 1)

    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test_vgpu", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vm_vgpu_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, image=None, count=None, threshold=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm_vgpu(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest_vm, "cleanup")
    @patch.object(LXDTest_vm, "test_vgpu", return_value=False)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vm_vgpu_failure(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, image=None, count=None, threshold=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vm_vgpu(args)
        self.assertEqual(cm.exception.code, 1)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, rootfs=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(
        os.environ,
        {"LXD_TEMPLATE": "template", "LXD_ROOTFS": "rootfs"},
        clear=True,
    )
    def test_test_lxd_environ_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, rootfs=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_args_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template="template", rootfs="rootfs")

        with self.assertRaises(SystemExit) as cm:
            test_lxd(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test", return_value=False)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_failure(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, rootfs=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd(args)
        self.assertEqual(cm.exception.code, 1)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test_vgpu", return_value=True)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vgpu_success(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, rootfs=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vgpu(args)
        self.assertEqual(cm.exception.code, 0)

    @patch.object(LXDTest, "cleanup")
    @patch.object(LXDTest, "test_vgpu", return_value=False)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.get_release_to_test", return_value="24.04")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_lxd_vgpu_failure(
        self,
        release_mock,
        codename_mock,
        test_mock,
        cleanup_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(template=None, rootfs=None)

        with self.assertRaises(SystemExit) as cm:
            test_lxd_vgpu(args)
        self.assertEqual(cm.exception.code, 1)

    @patch("os.system")
    @patch.object(KVMTest, "start", return_value=0)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.check_output", return_value="ppc64el")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_kvm_ppc64el_success(
        self,
        check_output_mock,
        codename_mock,
        start_mock,
        system_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(timeout=None, image=None, log_file=None)

        with self.assertRaises(SystemExit) as cm:
            test_kvm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch("os.system")
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch.object(KVMTest, "start", return_value=0)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.check_output", return_value="arm64")
    @patch.dict(
        os.environ, {"KVM_TIMEOUT": "1", "KVM_IMAGE": "image"}, clear=True
    )
    def test_test_kvm_environ_success(
        self,
        check_output_mock,
        codename_mock,
        start_mock,
        get_codename_mock,
        system_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(timeout=None, image=None, log_file=None)

        with self.assertRaises(SystemExit) as cm:
            test_kvm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch("os.system")
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch.object(KVMTest, "start", return_value=0)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.check_output", return_value="arm64")
    @patch.dict(
        os.environ, {"KVM_TIMEOUT": "bad", "KVM_IMAGE": "image"}, clear=True
    )
    def test_test_kvm_environ_timeout_fallback_success(
        self,
        check_output_mock,
        codename_mock,
        start_mock,
        get_codename_mock,
        system_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(timeout=None, image=None, log_file=None)

        with self.assertRaises(SystemExit) as cm:
            test_kvm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch("os.system")
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch.object(KVMTest, "start", return_value=0)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.check_output", return_value="arm64")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_kvm_args_success(
        self,
        check_output_mock,
        codename_mock,
        start_mock,
        get_codename_mock,
        system_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(timeout=1, image="image", log_file="file")

        with self.assertRaises(SystemExit) as cm:
            test_kvm(args)
        self.assertEqual(cm.exception.code, 0)

    @patch("os.system")
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch.object(KVMTest, "start", return_value=1)
    @patch("virtualization.get_codename_to_test", return_value="noble")
    @patch("virtualization.check_output", return_value="ppc64el")
    @patch.dict(os.environ, {}, clear=True)
    def test_test_kvm_failure(
        self,
        check_output_mock,
        codename_mock,
        start_mock,
        get_codename_mock,
        system_mock,
        logging_mock,
        print_mock,
    ):
        args = MagicMock(timeout=None, image=None, log_file=None)

        with self.assertRaises(SystemExit) as cm:
            test_kvm(args)
        self.assertEqual(cm.exception.code, 1)
