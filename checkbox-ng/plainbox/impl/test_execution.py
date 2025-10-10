# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import contextlib

from plainbox.impl.execution import (
    UnifiedRunner,
    get_execution_command_systemd_unit,
    get_execution_command_subshell,
)
from plainbox.impl.unit.job import InvalidJob

from unittest import TestCase, mock


class UnifiedRunnerTests(TestCase):
    def test_run_job_invalid_job(self):
        self_mock = mock.MagicMock()

        invalid_unit = mock.MagicMock(
            _data={"id": "generated_id_{param}"}, parameters={}
        )
        invalid_job = InvalidJob.from_unit(invalid_unit, errors=["Some error"])
        ui = mock.MagicMock()

        result = UnifiedRunner.run_job(self_mock, invalid_job, None, ui=ui)

        output_writer = self_mock._job_runner_ui_delegate
        self.assertTrue(output_writer.on_begin.called)
        # error is reported via the ui
        self.assertTrue(output_writer.on_chunk.called)
        self.assertTrue(output_writer.on_end.called)
        self.assertEqual(result.outcome, "fail")

    @mock.patch("shutil.which")
    @mock.patch(
        "plainbox.impl.execution.get_differential_execution_environment"
    )
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    def test_get_execution_command_systemd_unit_command_and_envvars(
        self, mock_on_ubuntucore, mock_get_diff_env, mock_shutil_which
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = False
        mock_get_diff_env.return_value = {"TEST_VAR": "test_value"}
        mock_shutil_which.return_value = "/usr/bin/plz-run"

        result = get_execution_command_systemd_unit(
            job, {}, "test_session", "/tmp/nest", "ubuntu", None
        )
        result = " ".join(result)

        # outside ubuntucore, there is no filesystem to mount
        self.assertNotIn("nsenter", result)

        self.assertIn("test_command", result)
        # user command are executed in a logged in slice/service
        self.assertIn("-pam", result)

    @mock.patch("shutil.which")
    @mock.patch(
        "plainbox.impl.execution.get_differential_execution_environment"
    )
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    @mock.patch("os.getenv")
    def test_get_execution_command_systemd_unit_nsenter_on_core(
        self,
        mock_os_getenv,
        mock_on_ubuntucore,
        mock_get_diff_env,
        mock_shutil_which,
    ):
        job = mock.Mock(shell="/bin/bash", command="test_command")
        mock_on_ubuntucore.return_value = True
        mock_os_getenv.return_value = "test_snap"
        mock_get_diff_env.return_value = {}

        def shutil_which(x):
            return "/bin/{}".format(x)

        mock_shutil_which.side_effect = shutil_which

        result = get_execution_command_systemd_unit(
            job, {}, "test_session", "/tmp/nest", "root", None
        )
        result = " ".join(result)

        # on ubuntucore, ensure we mount the frontend filesystem
        self.assertIn("nsenter", result)
        self.assertIn("/run/snapd/ns/test_snap.mnt", result)

        self.assertIn("test_command", result)
        # don't log in root commands
        self.assertNotIn("-pam", result)

    @mock.patch(
        "plainbox.impl.execution.get_differential_execution_environment"
    )
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    def test_get_execution_command_subshell_with_user(
        self, mock_on_ubuntucore, mock_get_diff_env
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = False
        mock_get_diff_env.return_value = {"TEST_VAR": "test_value"}

        result = get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", "ubuntu", None
        )
        result = " ".join(result)

        self.assertIn("sudo", result)
        self.assertIn("TEST_VAR=test_value", result)
        self.assertIn("test_command", result)
        self.assertNotIn("aa-exec", result)

    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    def test_get_execution_command_subshell_no_user(
        self, mock_on_ubuntucore, mock_get_env
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = False
        mock_get_env.return_value = {"TEST_VAR": "test_value"}

        result = get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", None, None
        )
        result = " ".join(result)

        self.assertNotIn("sudo", result)
        self.assertIn("TEST_VAR=test_value", result)
        self.assertIn("test_command", result)
        self.assertNotIn("aa-exec", result)

    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    def test_get_execution_command_subshell_on_core(
        self, mock_on_ubuntucore, mock_get_env
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = True
        mock_get_env.return_value = {"TEST_VAR": "test_value"}

        result = get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", None, None
        )
        result = " ".join(result)

        self.assertNotIn("sudo", result)
        self.assertIn("TEST_VAR=test_value", result)
        self.assertIn("test_command", result)
        self.assertIn("aa-exec -p unconfined", result)

    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.get_execution_command_subshell")
    @mock.patch("plainbox.impl.execution.get_execution_command_systemd_unit")
    @mock.patch("getpass.getuser")
    def test_execute_job_subshell(
        self,
        getuser_mock,
        get_execution_command_systemd_unit_mock,
        get_execution_command_subshell_mock,
        get_execution_environment_mock,
    ):
        @contextlib.contextmanager
        def configured_filesystem_mock(self, *args, **kwargs):
            yield

        self_mock = mock.Mock(configured_filesystem=configured_filesystem_mock)
        self_mock._user_provider.return_value = None

        job_mock = mock.Mock(user="ubuntu")
        job_mock.get_flag_set.return_value = {"preserve-cwd"}
        getuser_mock.return_value = "ubuntu"

        get_execution_command_subshell_mock.side_effect = Exception("subshell")
        get_execution_command_systemd_unit_mock.side_effect = Exception(
            "systemd"
        )

        with self.assertRaises(Exception) as e:
            UnifiedRunner.execute_job(self_mock, job_mock, {}, mock.Mock())

        self.assertEqual(str(e.exception), "subshell")

    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.get_execution_command_subshell")
    @mock.patch("plainbox.impl.execution.get_execution_command_systemd_unit")
    @mock.patch("getpass.getuser")
    def test_execute_job_systemd(
        self,
        getuser_mock,
        get_execution_command_systemd_unit_mock,
        get_execution_command_subshell_mock,
        get_execution_environment_mock,
    ):
        @contextlib.contextmanager
        def configured_filesystem_mock(self, *args, **kwargs):
            yield

        self_mock = mock.Mock(configured_filesystem=configured_filesystem_mock)
        self_mock._user_provider.return_value = None

        job_mock = mock.Mock(user="ubuntu")
        job_mock.get_flag_set.return_value = {"preserve-cwd"}
        getuser_mock.return_value = "ubuntu"

        get_execution_command_subshell_mock.side_effect = Exception("subshell")
        get_execution_command_systemd_unit_mock.side_effect = Exception(
            "systemd"
        )

        with self.assertRaises(Exception) as e:
            UnifiedRunner.execute_job(
                self_mock, job_mock, {}, mock.Mock(), systemd_unit=True
            )

        self.assertEqual(str(e.exception), "systemd")
