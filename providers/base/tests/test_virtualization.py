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

import itertools
from unittest import TestCase
from unittest.mock import patch, MagicMock

from virtualization import LXDTest, LXDTest_vm


class TestLXDTest(TestCase):
    @patch(
        "virtualization.RunCommand",
        return_value=MagicMock(returncode=0, stdout="abc", stderr=None),
    )
    @patch("virtualization.logging")
    def test_run_command_no_stderr(self, logging_mock, run_command_mock):
        result = LXDTest.run_command(MagicMock(), "command", log_stderr=True)

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_no_log_stderr(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 1
        task.stdout = "abc"
        task.stderr = None

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=False
        )

        self.assertFalse(command_result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_error(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 1
        task.stdout = "abc"
        task.stderr = "some error"

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.error.called)
        self.assertFalse(command_result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_ok(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 0
        task.stdout = "abc"
        task.stderr = "some error"

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(command_result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_guest_ok(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 0
        task.stdout = "abc"
        task.stderr = "some error"

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=True, on_guest=True
        )

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(command_result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_ok_no_stdout(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 0
        task.stdout = ""
        task.stderr = "some error"

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(command_result)

    @patch("virtualization.RunCommand")
    @patch("virtualization.logging")
    def test_run_command_ok_no_output(self, logging_mock, run_command_mock):
        task = run_command_mock()
        task.returncode = 0
        task.stdout = ""
        task.stderr = ""

        command_result = LXDTest.run_command(
            MagicMock(), "command", log_stderr=True
        )

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(command_result)

    @patch("virtualization.logging")
    def test_init_lxd_already_started(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True]

        result = LXDTest.init_lxd(self_mock)

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_init_lxd_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, True]

        result = LXDTest.init_lxd(self_mock)

        self.assertTrue(logging_mock.debug.called)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_init_lxd_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False, False]

        result = LXDTest.init_lxd(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_retrieve_template_not_provided(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_url = None

        result = LXDTest.retrieve_template(self_mock)
        self.assertTrue(result)

    @patch("os.path.isfile", return_value=True)
    @patch("virtualization.logging")
    def test_retrieve_template_already_exists(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.template_url = "path/to/template"

        result = LXDTest.retrieve_template(self_mock)
        self.assertTrue(result)

    @patch("os.path.isfile", return_value=False)
    @patch("virtualization.logging")
    def test_retrieve_template_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.template_url = "path/to/template"
        self_mock.download_images.return_value = False

        result = LXDTest.retrieve_template(self_mock)
        self.assertFalse(result)

    @patch("os.path.isfile", return_value=False)
    @patch("virtualization.logging")
    def test_retrieve_template_success(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.template_url = "path/to/template"
        self_mock.download_images.return_value = "/tmp/template"

        result = LXDTest.retrieve_template(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_retrieve_image_not_provided(self, logging_mock):
        self_mock = MagicMock()
        self_mock.image_url = None

        result = LXDTest.retrieve_image(self_mock)
        self.assertTrue(result)

    @patch("os.path.isfile", return_value=True)
    @patch("virtualization.logging")
    def test_retrieve_image_already_exists(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.image_url = "path/to/image"

        result = LXDTest.retrieve_image(self_mock)
        self.assertTrue(result)

    @patch("os.path.isfile", return_value=False)
    @patch("virtualization.logging")
    def test_retrieve_image_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.image_url = "path/to/image"
        self_mock.download_images.return_value = False

        result = LXDTest.retrieve_image(self_mock)
        self.assertFalse(result)

    @patch("os.path.isfile", return_value=False)
    @patch("virtualization.logging")
    def test_retrieve_image_success(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.image_url = "path/to/image"
        self_mock.download_images.return_value = "/tmp/image"

        result = LXDTest.retrieve_image(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_insert_images_import_tarballs_ok(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.image_alias = "alias"
        self_mock.run_command.return_value = True

        result = LXDTest.insert_images(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_insert_images_import_tarballs_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.image_alias = "alias"
        self_mock.run_command.return_value = False

        result = LXDTest.insert_images(self_mock)
        self.assertFalse(result)

    @patch("virtualization.range", return_value=[0])
    @patch("virtualization.logging")
    def test_insert_images_remote_failure(self, logging_mock, range_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None
        self_mock.default_remote = "remote"
        self_mock.os_version = "24.04"
        self_mock.image_alias = "alias"
        self_mock.run_command.side_effect = itertools.repeat(False)

        result = LXDTest.insert_images(self_mock)
        self.assertFalse(result)

    @patch("virtualization.range", return_value=[0])
    @patch("virtualization.logging")
    def test_insert_images_remote_success(self, logging_mock, range_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None
        self_mock.default_remote = "remote"
        self_mock.os_version = "24.04"
        self_mock.image_alias = "alias"
        self_mock.run_command.return_value = True

        result = LXDTest.insert_images(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_setup_fail_init_lxd(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = False

        result = LXDTest.setup(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_setup_fail_retrieve_template(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = False

        result = LXDTest.setup(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_setup_fail_retrieve_image(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = False

        result = LXDTest.setup(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_setup_fail_insert_images(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = False

        result = LXDTest.setup(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_setup_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.init_lxd.return_value = True
        self_mock.retrieve_template.return_value = True
        self_mock.retrieve_image.return_value = True
        self_mock.insert_images.return_value = True

        result = LXDTest.setup(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_add_gpu_device_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        result = LXDTest.add_gpu_device(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_add_gpu_device_ok(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        result = LXDTest.add_gpu_device(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_add_gpu_device_pci_ok(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.add_gpu_device(self_mock, gpu_pci)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_add_apt_repo_gpg_import_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [False]

        name = "repo"
        url = "http://www.repo.com"
        gpg = "http://www.repo.com/key"
        fingerprint = "fingerprint"
        result = LXDTest.add_apt_repo(self_mock, name, url, gpg, fingerprint)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_add_apt_repo_pinfile_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False]

        name = "repo"
        url = "http://www.repo.com"
        gpg = "http://www.repo.com/key"
        fingerprint = "fingerprint"
        pinfile = "bad pinfile, bad"
        result = LXDTest.add_apt_repo(
            self_mock, name, url, gpg, fingerprint, pinfile
        )
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_add_apt_repo_source_list_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False]

        name = "repo"
        url = "http://www.repo.com"
        gpg = "http://www.repo.com/key"
        fingerprint = "fingerprint"
        result = LXDTest.add_apt_repo(self_mock, name, url, gpg, fingerprint)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_add_apt_repo_cache_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, False]

        name = "repo"
        url = "http://www.repo.com"
        gpg = "http://www.repo.com/key"
        fingerprint = "fingerprint"
        result = LXDTest.add_apt_repo(self_mock, name, url, gpg, fingerprint)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_add_apt_repo_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True, True, True]

        name = "repo"
        url = "http://www.repo.com"
        gpg = "http://www.repo.com/key"
        fingerprint = "fingerprint"
        pinfile = "http://www.repo.com/pin"
        result = LXDTest.add_apt_repo(
            self_mock, name, url, gpg, fingerprint, pinfile
        )
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_configure_amd_gpu_no_pci(self, logging_mock):
        self_mock = MagicMock()

        gpu_pci = None
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[False, False])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_no_dev_files(self, logging_mock, isfile_mock):
        self_mock = MagicMock()

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)
        self.assertTrue(isfile_mock.called)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_add_gpu_device_fail(
        self, logging_mock, isfile_mock
    ):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = False

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_add_files_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [False, False]

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_apt_repo_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True]
        self_mock.add_apt_repo.return_value = False

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)
        self.assertTrue(self_mock.add_apt_repo.called)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_rocm_install_fail(
        self, logging_mock, isfile_mock
    ):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, False]
        self_mock.add_apt_repo.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_compile_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, False]
        self_mock.add_apt_repo.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_restart_fail(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, True, False]
        self_mock.add_apt_repo.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertFalse(result)

    @patch("os.path.isfile", side_effect=[True, True])
    @patch("virtualization.logging")
    def test_configure_amd_gpu_success(self, logging_mock, isfile_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, True, True]
        self_mock.add_apt_repo.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_amd_gpu(self_mock, gpu_pci)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_add_gpu_device_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.add_gpu_device.return_value = False

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_nvidia_runtime_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [False]

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_repo_fail(self, logging_mock, os_uname_mock):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True]
        self_mock.add_apt_repo.return_value = False

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)
        self.assertTrue(self_mock.add_apt_repo.called)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch("virtualization.logging")
    def test_configure_nvidia_cuda_install_fail(
        self, logging_mock, os_uname_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, False]
        self_mock.add_apt_repo.return_value = True

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch(
        "subprocess.run", side_effect=[MagicMock(returncode=0, stdout="7.4")]
    )
    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_compile_fail(
        self, logging_mock, subprocess_run_mock, os_uname_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, False]
        self_mock.add_apt_repo.return_value = True

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch(
        "subprocess.run", side_effect=[MagicMock(returncode=0, stdout="7.4")]
    )
    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_restart_fail(
        self, logging_mock, subprocess_run_mock, os_uname_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, False]
        self_mock.add_apt_repo.return_value = True

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertFalse(result)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch(
        "subprocess.run", side_effect=[MagicMock(returncode=0, stdout="7.4")]
    )
    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_success(
        self, logging_mock, subprocess_run_mock, os_uname_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, True]
        self_mock.add_apt_repo.return_value = True

        gpu_pci = "000057:00.0"
        result = LXDTest.configure_nvidia_gpu(self_mock, gpu_pci)
        self.assertTrue(result)

    @patch("os.uname", return_value=MagicMock(machine="x86_64"))
    @patch("subprocess.run", side_effect=[MagicMock(returncode=1)])
    @patch("virtualization.logging")
    def test_configure_nvidia_gpu_cuda_arch_fallback_success(
        self, logging_mock, subprocess_run_mock, os_uname_mock
    ):
        self_mock = MagicMock()
        self_mock.os_version = "24.04"
        self_mock.add_gpu_device.return_value = True
        self_mock.run_command.side_effect = [True, True, True, True, True]
        self_mock.add_apt_repo.return_value = True

        result = LXDTest.configure_nvidia_gpu(self_mock)
        self.assertTrue(result)

    @patch("urllib.request.urlretrieve", side_effect=IOError())
    @patch("virtualization.logging")
    def test_download_images_download_fail(
        self, logging_mock, urlretrieve_mock
    ):
        self_mock = MagicMock()

        url = "url/to/file"
        filename = "path/to/file"
        result = LXDTest.download_images(self_mock, url, filename)
        self.assertFalse(result)

    @patch("urllib.request.urlretrieve", side_effect=ValueError())
    @patch("virtualization.logging")
    def test_download_images_url_fail(self, logging_mock, urlretrieve_mock):
        self_mock = MagicMock()

        url = "url/to/file"
        filename = "path/to/file"
        result = LXDTest.download_images(self_mock, url, filename)
        self.assertFalse(result)

    @patch("os.path.isfile", return_value=False)
    @patch("urllib.request.urlretrieve")
    @patch("virtualization.logging")
    def test_download_images_no_file(
        self, logging_mock, urlretrieve_mock, isfile_mock
    ):
        self_mock = MagicMock()

        url = "url/to/file"
        filename = "path/to/file"
        result = LXDTest.download_images(self_mock, url, filename)
        self.assertFalse(result)

    @patch("os.path.isfile", return_value=True)
    @patch("urllib.request.urlretrieve")
    @patch("virtualization.logging")
    def test_download_images_success(
        self, logging_mock, urlretrieve_mock, isfile_mock
    ):
        self_mock = MagicMock()

        url = "url/to/file"
        filename = "path/to/file"
        result = LXDTest.download_images(self_mock, url, filename)
        self.assertEqual(result, filename)

    @patch("virtualization.logging")
    def test_cleanup(self, logging_mock):
        self_mock = MagicMock()
        LXDTest.cleanup(self_mock)
        self.assertTrue(self_mock.run_command.called)

    @patch("virtualization.logging")
    def test_launch_setup_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = False

        result = LXDTest.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_launch_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.return_value = False

        result = LXDTest.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_list_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.side_effect = [True, False]

        result = LXDTest.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.run_command.side_effect = [True, True]

        result = LXDTest.launch(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_test_launch_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        result = LXDTest.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_test_exec_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = False

        result = LXDTest.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_test_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.run_command.return_value = True

        result = LXDTest.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_test_vgpu_launch_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        gpu_vendor = "nvidia"
        result = LXDTest.test_vgpu(self_mock, gpu_vendor)
        self.assertFalse(result)

    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_invalid_vendor(self, logging_mock, sleep_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        gpu_vendor = "not a gpu vendor for sure"
        result = LXDTest.test_vgpu(self_mock, gpu_vendor)
        self.assertFalse(result)

    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_nvidia_configure_fail(self, logging_mock, sleep_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.configure_nvidia_gpu.return_value = False

        gpu_vendor = "nvidia"
        result = LXDTest.test_vgpu(self_mock, gpu_vendor)
        self.assertFalse(result)

    @patch("time.time", side_effect=[0, 1])
    @patch("virtualization.range", return_value=[0])
    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_exec_fail(
        self, logging_mock, sleep_mock, range_mock, time_mock
    ):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.configure_nvidia_gpu.return_value = True
        self_mock.run_command.return_value = False

        gpu_vendor = "nvidia"
        result = LXDTest.test_vgpu(self_mock, gpu_vendor)
        self.assertFalse(result)

    @patch("time.time", side_effect=[0, 2])
    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_runtime_fail(self, logging_mock, sleep_mock, time_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.configure_nvidia_gpu.return_value = True
        self_mock.run_command.return_value = True

        gpu_vendor = "nvidia"
        threshold_sec = 1
        result = LXDTest.test_vgpu(
            self_mock, gpu_vendor, run_count=1, threshold_sec=threshold_sec
        )
        self.assertFalse(result)
        self.assertTrue(logging_mock.error.called)

    @patch("time.time", side_effect=[0, 1])
    @patch("virtualization.range", return_value=[0])
    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_nvidia_success(
        self, logging_mock, sleep_mock, range_mock, time_mock
    ):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.configure_nvidia_gpu.return_value = True
        self_mock.run_command.return_value = True

        gpu_vendor = "nvidia"
        threshold_sec = 2
        result = LXDTest.test_vgpu(
            self_mock, gpu_vendor, threshold_sec=threshold_sec
        )
        self.assertTrue(result)

    @patch("time.time", side_effect=[0, 1])
    @patch("virtualization.range", return_value=[0])
    @patch("time.sleep")
    @patch("virtualization.logging")
    def test_test_vgpu_amd_success(
        self, logging_mock, sleep_mock, range_mock, time_mock
    ):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.configure_amd_gpu.return_value = True
        self_mock.run_command.return_value = True

        gpu_vendor = "amd"
        threshold_sec = 2
        result = LXDTest.test_vgpu(
            self_mock, gpu_vendor, threshold_sec=threshold_sec
        )
        self.assertTrue(result)


class TestLXDTest_vm(TestCase):

    @patch("virtualization.logging")
    def test_insert_images_not_provided(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = None
        self_mock.image_tarball = None

        result = LXDTest_vm.insert_images(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_insert_images_import_failure(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.run_command.return_value = False

        result = LXDTest_vm.insert_images(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_insert_images_import_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.template_tarball = "template"
        self_mock.image_tarball = "image"
        self_mock.run_command.return_value = True

        result = LXDTest_vm.insert_images(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_launch_setup_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = False

        result = LXDTest_vm.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_local_import_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image"
        self_mock.template_url = "template"
        self_mock.run_command.return_value = False

        result = LXDTest_vm.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_start_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image"
        self_mock.template_url = "template"
        self_mock.run_command.side_effect = [True, False]

        result = LXDTest_vm.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_list_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = "image"
        self_mock.template_url = "template"
        self_mock.run_command.side_effect = [True, True, False]

        result = LXDTest_vm.launch(self_mock)
        self.assertFalse(result)

    @patch("virtualization.logging")
    def test_launch_remote_import_success(self, logging_mock):
        self_mock = MagicMock()
        self_mock.setup.return_value = True
        self_mock.image_url = None
        self_mock.template_url = None
        self_mock.run_command.side_effect = [True, True, True]

        result = LXDTest_vm.launch(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_add_gpu_device_stop_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = False

        result = LXDTest_vm.add_gpu_device(self_mock)
        self.assertFalse(result)

    @patch("virtualization.super")
    @patch("virtualization.logging")
    def test_add_gpu_device_super_fail(self, logging_mock, super_mock):
        self_mock = MagicMock()
        self_mock.run_command.return_value = True
        super_mock().add_gpu_device.return_value = False

        result = LXDTest_vm.add_gpu_device(self_mock)
        self.assertFalse(result)

    @patch("virtualization.super")
    @patch("virtualization.logging")
    def test_add_gpu_device_start_fail(self, logging_mock, super_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, False]
        super_mock().add_gpu_device.return_value = True

        result = LXDTest_vm.add_gpu_device(self_mock)
        self.assertFalse(result)

    @patch("virtualization.super")
    @patch("virtualization.logging")
    def test_add_gpu_device_success(self, logging_mock, super_mock):
        self_mock = MagicMock()
        self_mock.run_command.side_effect = [True, True]
        super_mock().add_gpu_device.return_value = True

        result = LXDTest_vm.add_gpu_device(self_mock)
        self.assertTrue(result)

    @patch("virtualization.logging")
    def test_test_launch_fail(self, logging_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = False

        result = LXDTest_vm.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertFalse(result)

    @patch("time.sleep")
    @patch("virtualization.print")
    @patch("virtualization.logging")
    def test_test_failure(self, logging_mock, print_mock, time_sleep_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = itertools.repeat(False)

        result = LXDTest_vm.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertFalse(result)

    @patch("time.sleep")
    @patch("virtualization.print")
    @patch("virtualization.logging")
    def test_test_success(self, logging_mock, print_mock, time_sleep_mock):
        self_mock = MagicMock()
        self_mock.launch.return_value = True
        self_mock.name = "vm name"
        self_mock.run_command.side_effect = itertools.repeat(True)

        result = LXDTest_vm.test(self_mock)
        self.assertTrue(self_mock.launch.called)
        self.assertTrue(result)
        self.assertTrue(print_mock.called)
