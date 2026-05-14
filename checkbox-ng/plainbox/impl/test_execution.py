# This file is part of Checkbox.
#
# Copyright 2024-2025 Canonical Ltd.
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
import os
from pathlib import Path
from unittest import TestCase, mock

from plainbox.impl.execution import (
    FakeJobRunner,
    MountingStrategy,
    UnifiedRunner,
    add_to_environment,
    dangerous_nsenter,
    get_execution_command_subshell,
    get_execution_command_systemd_unit,
    get_execution_environment,
)
from plainbox.impl.unit.job import InvalidJob


@contextlib.contextmanager
def empty_context(path, **kwargs):
    yield path


# we test this separately and mock it globally here to vaoid risking actually
# calling it in tests
@mock.patch("plainbox.impl.execution.dangerous_nsenter", new=empty_context)
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

    @mock.patch("os.chmod")
    @mock.patch("tempfile.NamedTemporaryFile")
    @mock.patch("shutil.which")
    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    @mock.patch("plainbox.impl.execution.get_snap_base")
    @mock.patch("plainbox.impl.unit.unit.get_snap_base")
    def test_get_execution_command_systemd_unit_command_and_envvars(
        self,
        mock_get_snap_base_unit,
        mock_get_snap_base_execution,
        mock_on_ubuntucore,
        mock_get_diff_env,
        mock_shutil_which,
        mock_temp_file,
        mock_chmod,
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = True
        mock_get_snap_base_unit.return_value = (
            mock_get_snap_base_execution.return_value
        ) = "core24"
        mock_get_diff_env.return_value = {"TEST_VAR": "test_value"}
        mock_shutil_which.return_value = "/usr/bin/plz-run"

        mock_file = mock.MagicMock()
        mock_file.name = "/var/tmp/job_command_test.sh"
        mock_temp_file().__enter__.return_value = mock_file

        with get_execution_command_systemd_unit(
            job, {}, "test_session", "/tmp/nest", "ubuntu", None
        ) as result:
            result = " ".join(result)

        result += " ".join(str(x) for x in mock_file.write.call_args_list)

        self.assertIn("nsenter", result)

        self.assertIn("test_command", result)
        # user command are executed in a logged in slice/service
        self.assertIn("-pam", result)

    @mock.patch("os.chmod")
    @mock.patch("tempfile.NamedTemporaryFile")
    @mock.patch("shutil.which")
    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    def test_get_execution_command_systemd_unit_non_core(
        self,
        mock_on_ubuntucore,
        mock_get_diff_env,
        mock_shutil_which,
        mock_temp_file,
        mock_chmod,
    ):
        job = mock.Mock(shell="bash", command="test_command")
        mock_on_ubuntucore.return_value = False
        mock_get_diff_env.return_value = {"TEST_VAR": "test_value"}
        mock_shutil_which.return_value = "/usr/bin/plz-run"

        mock_file = mock.MagicMock()
        mock_file.name = "/var/tmp/job_command_test.sh"
        mock_temp_file().__enter__.return_value = mock_file

        def extra_envvars():
            return []

        with get_execution_command_systemd_unit(
            job, {}, "test_session", "/tmp/nest", "ubuntu", extra_envvars
        ) as result:
            result = " ".join(result)

        result += " ".join(str(x) for x in mock_file.write.call_args_list)

        self.assertNotIn("nsenter", result)

        self.assertIn("test_command", result)
        # user command are executed in a logged in slice/service
        self.assertIn("-pam", result)

    @mock.patch("os.chmod")
    @mock.patch("tempfile.NamedTemporaryFile")
    @mock.patch("shutil.which")
    @mock.patch("plainbox.impl.execution.get_execution_environment")
    @mock.patch("plainbox.impl.execution.on_ubuntucore")
    @mock.patch("plainbox.impl.execution.get_snap_base")
    @mock.patch("plainbox.impl.execution.get_checkbox_runtime_path")
    @mock.patch("os.getenv")
    def test_get_execution_command_systemd_unit_nsenter_on_core(
        self,
        mock_os_getenv,
        mock_get_checkbox_runtime_path,
        mock_get_snap_base,
        mock_on_ubuntucore,
        mock_get_diff_env,
        mock_shutil_which,
        mock_temp_file,
        mock_chmod,
    ):
        job = mock.Mock(shell="/bin/bash", command="test_command")
        mock_on_ubuntucore.return_value = True
        mock_os_getenv.return_value = "test_snap"
        mock_get_diff_env.return_value = {}

        mock_get_checkbox_runtime_path.return_value = Path("")

        def shutil_which(x):
            return "/bin/{}".format(x)

        mock_shutil_which.side_effect = shutil_which

        mock_file = mock.MagicMock()
        mock_file.name = "/var/tmp/job_command_test.sh"
        mock_temp_file().__enter__.return_value = mock_file

        with get_execution_command_systemd_unit(
            job, {}, "test_session", "/tmp/nest", "root", None
        ) as result:
            result = " ".join(result)
        result += " ".join(str(x) for x in mock_file.write.call_args_list)

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

        with get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", "ubuntu", None
        ) as result:
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

        with get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", None, None
        ) as result:
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

        with get_execution_command_subshell(
            job, {}, "test_session", "/tmp/nest", None, None
        ) as result:
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
        def empty_ctx_manager(self, *args, **kwargs):
            yield

        configured_filesystem_mock = empty_ctx_manager
        get_proper_job_cwd_mock = empty_ctx_manager

        self_mock = mock.Mock(
            configured_filesystem=configured_filesystem_mock,
            get_proper_job_cwd=get_proper_job_cwd_mock,
        )
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
        def empty_ctx_manager(self, *args, **kwargs):
            yield

        configured_filesystem_mock = empty_ctx_manager
        get_proper_job_cwd_mock = empty_ctx_manager

        self_mock = mock.Mock(
            configured_filesystem=configured_filesystem_mock,
            get_proper_job_cwd=get_proper_job_cwd_mock,
        )
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
                self_mock, job_mock, {}, mock.Mock(), as_systemd_unit=True
            )
        self.assertEqual(str(e.exception), "systemd")

    @mock.patch("os.getcwd")
    def test_get_proper_job_cwd_preserve_cwd(self, os_cwd_mock):
        self_mock = mock.Mock()
        job_mock = mock.Mock()
        job_mock.get_flag_set.return_value = {"preserve-cwd"}
        with UnifiedRunner.get_proper_job_cwd(self_mock, job_mock) as cwd:
            self.assertEqual(cwd, os_cwd_mock())

    @mock.patch("os.getcwd")
    @mock.patch("os.getenv")
    @mock.patch("os.chmod")
    def test_get_proper_job_cwd_snap(
        self, chmod_mock, os_getenv_mock, os_cwd_mock
    ):
        self_mock = mock.Mock()
        job_mock = mock.Mock()
        job_mock.get_flag_set.return_value = {}
        os_getenv_mock.return_value = "/snap/checkbox24"

        class TemporaryDirectoryMock:
            def __init__(self, suffix, prefix, dir, *args, **kwargs):
                self.dir = dir

            def __enter__(self):
                return self.dir + "/some"

            def __exit__(self, *args): ...

        with mock.patch(
            "tempfile.TemporaryDirectory", new=TemporaryDirectoryMock
        ) as tmp:
            with UnifiedRunner.get_proper_job_cwd(self_mock, job_mock) as cwd:
                self.assertTrue(str(cwd).startswith("/var/tmp"))
            self.assertTrue(self_mock._check_leftovers.called)


class TestDangerousNsenter(TestCase):
    def call_args_to_string(self, call_arg):
        return " ".join(str(x) for x in call_arg[0][0])

    @mock.patch("plainbox.impl.execution.check_output")
    @mock.patch("plainbox.impl.execution.check_call")
    @mock.patch("plainbox.impl.execution.run")
    @mock.patch("shutil.which")
    def test_dangerous_nsenter_cleanup(
        self, which_mock, run_mock, check_call_mock, check_output_mock
    ):
        which_mock.return_value = "/bin/plz-run"
        with self.assertRaises(ValueError):
            with dangerous_nsenter("/var/tmp/nsenter_dangerous"):
                # prepared dangerous nsenter is copied somewhere, made extable
                # and given caps
                subprocess_calls = (
                    run_mock.call_args_list
                    + check_call_mock.call_args_list
                    + check_output_mock.call_args_list
                )
                subprocess_calls = [
                    self.call_args_to_string(arg) for arg in subprocess_calls
                ]
                # all calls must be executed outside the sandbox as paths are
                # root relative
                not_plz_running = [
                    arg for arg in subprocess_calls if "plz-run" not in arg
                ]
                self.assertFalse(not_plz_running)
                subprocess_calls_str = "\n".join(
                    str(arg) for arg in subprocess_calls
                )
                self.assertIn("cp", subprocess_calls_str)
                self.assertIn("nsenter", subprocess_calls_str)
                self.assertIn("chmod", subprocess_calls_str)
                self.assertIn("777", subprocess_calls_str)
                # this makes it possible to users to call this nsenter.
                # This is the dangerous part
                self.assertIn("cap_sys_admin", subprocess_calls_str)
                run_mock.reset_mock()
                check_call_mock.reset_mock()
                check_output_mock.reset_mock()
                raise ValueError("Ensure decorator always deletes the binary")

        subprocess_calls = (
            run_mock.call_args_list
            + check_call_mock.call_args_list
            + check_output_mock.call_args_list
        )
        subprocess_calls_str = "\n".join(str(arg) for arg in subprocess_calls)
        self.assertIn("rm", subprocess_calls_str)
        self.assertIn("nsenter", subprocess_calls_str)


class TestMountingStrategy(TestCase):
    def test_dont_mount(self):
        self.assertEqual(
            MountingStrategy.from_user_core("root", False, None),
            MountingStrategy.DONT_MOUNT,
        )

    def test_mount_root(self):
        self.assertEqual(
            MountingStrategy.from_user_core("root", True, "core16"),
            MountingStrategy.MOUNT_ROOT,
        )

    def test_mount_dangerous(self):
        self.assertEqual(
            MountingStrategy.from_user_core("ubuntu", True, "core16"),
            MountingStrategy.MOUNT_DANGEROUS_NSENTER,
        )

    def test_mount_ambient(self):
        self.assertEqual(
            MountingStrategy.from_user_core("ubuntu", True, "core24"),
            MountingStrategy.MOUNT_AMBIENT_CAPABILITIES,
        )


class TestAddToEnvironment(TestCase):
    def test_no_values(self):
        env = {}
        self.assertEqual(env, add_to_environment(env, "some", []))

    def test_not_present(self):
        env = add_to_environment({}, "PATH", ["some", "path"])
        self.assertIn("some", env["PATH"])
        self.assertIn("path", env["PATH"])

    def test_present(self):
        og_path = os.pathsep.join(["og_path1", "og_path2"])
        env = add_to_environment({"PATH": og_path}, "PATH", ["some", "path"])
        new_path = env["PATH"].split(os.pathsep)
        self.assertIn("og_path1", new_path)
        self.assertIn("og_path2", new_path)
        self.assertIn("some", new_path)
        self.assertIn("path", new_path)


class TestGetExecutionEnvironment(TestCase):
    def setUp(self):
        self.job = mock.Mock()
        self.job.get_flag_set.return_value = set()
        self.job.provider.gettext_domain = None
        self.job.provider.locale_dir = None
        self.job.provider.extra_PYTHONPATH = []
        self.job.provider.extra_PATH = []
        self.job.provider.extra_LD_LIBRARY_PATH = []
        self.job.provider.extra_snap_environment = {}
        self.job.provider.data_dir = None
        self.job.provider.units_dir = None
        self.job.provider.CHECKBOX_SHARE = None

    @mock.patch.dict(os.environ, {"ORIGINAL_ENV": "value"}, clear=True)
    @mock.patch("plainbox.impl.execution.WellKnownDirsHelper")
    def test_basic_environment(self, mock_well_known):
        mock_well_known.session_share.return_value = "/session/share"

        env = get_execution_environment(
            self.job, None, "test_session", "/nest"
        )

        self.assertIn("ORIGINAL_ENV", env)
        self.assertEqual(env["ORIGINAL_ENV"], "value")
        self.assertEqual(env["PLAINBOX_SESSION_SHARE"], "/session/share")
        self.assertIn("/nest", env["PATH"])
        mock_well_known.session_share.assert_called_once_with("test_session")

    @mock.patch.dict(os.environ, {"SNAP": "/snap/checkbox24"}, clear=True)
    @mock.patch("plainbox.impl.execution.get_checkbox_runtime_path")
    @mock.patch("plainbox.impl.execution.WellKnownDirsHelper")
    def test_checkbox_runtime_in_snap(
        self, mock_well_known, mock_runtime_path
    ):
        mock_well_known.session_share.return_value = "/session/share"
        mock_runtime_path.return_value = Path("/snap/checkbox24/current")

        env = get_execution_environment(
            self.job, None, "test_session", "/nest"
        )

        self.assertEqual(env["CHECKBOX_RUNTIME"], "/snap/checkbox24/current")

    @mock.patch.dict(
        os.environ, {"EXISTING_VAR": "original_value"}, clear=True
    )
    @mock.patch("plainbox.impl.execution.WellKnownDirsHelper")
    def test_environ_dict_does_not_override_existing(self, mock_well_known):
        mock_well_known.session_share.return_value = "/session/share"

        environ = {"EXISTING_VAR": "new_value"}

        env = get_execution_environment(
            self.job, environ, "test_session", "/nest"
        )

        self.assertEqual(env["EXISTING_VAR"], "original_value")


@mock.patch("plainbox.impl.execution.dangerous_nsenter", new=empty_context)
class FakeJobRunnerTests(TestCase):
    def test_run_job_non_resource_as_systemd_unit_false(self):
        """Test FakeJobRunner passes as_systemd_unit=False to parent for non-resource jobs."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "shell"
        job_state = mock.MagicMock()

        with mock.patch.object(
            UnifiedRunner, "run_job", return_value=mock.MagicMock()
        ) as mock_parent_run_job:
            fake_runner.run_job(job, job_state, as_systemd_unit=False)

            mock_parent_run_job.assert_called_once_with(
                job, job_state, None, None, False
            )

    def test_run_job_non_resource_as_systemd_unit_true(self):
        """Test FakeJobRunner passes as_systemd_unit=True to parent for non-resource jobs."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "shell"
        job_state = mock.MagicMock()

        with mock.patch.object(
            UnifiedRunner, "run_job", return_value=mock.MagicMock()
        ) as mock_parent_run_job:
            fake_runner.run_job(job, job_state, as_systemd_unit=True)

            mock_parent_run_job.assert_called_once_with(
                job, job_state, None, None, True
            )

    def test_run_job_resource_default_as_systemd_unit(self):
        """Test FakeJobRunner creates fake resource for resource jobs (default as_systemd_unit)."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "resource"
        job.partial_id = "some_resource"
        job_state = mock.MagicMock()

        result = fake_runner.run_job(job, job_state)

        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.return_code, 0)
        self.assertEqual(len(result.io_log), 1)
        self.assertEqual(result.io_log[0].stream_name, "stdout")
        self.assertEqual(result.io_log[0].data, b"a: b\n")

    def test_run_job_graphics_card_resource(self):
        """Test FakeJobRunner creates two resource objects for graphics_card."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "resource"
        job.partial_id = "graphics_card"
        job_state = mock.MagicMock()

        result = fake_runner.run_job(job, job_state)

        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.return_code, 0)
        self.assertEqual(len(result.io_log), 3)
        self.assertEqual(result.io_log[0].stream_name, "stdout")
        self.assertEqual(result.io_log[0].data, b"a: b\n")
        self.assertEqual(result.io_log[1].stream_name, "stdout")
        self.assertEqual(result.io_log[1].data, b"\n")
        self.assertEqual(result.io_log[2].stream_name, "stdout")
        self.assertEqual(result.io_log[2].data, b"a: c\n")

    def test_run_job_resource_with_environ_and_ui(self):
        """Test FakeJobRunner creates fake resource with environ and ui parameters."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "resource"
        job.partial_id = "test_resource"
        job_state = mock.MagicMock()
        environ = {"TEST": "value"}
        ui = mock.MagicMock()

        result = fake_runner.run_job(job, job_state, environ, ui)

        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.return_code, 0)

    def test_run_job_non_resource_with_all_parameters(self):
        """Test FakeJobRunner passes all parameters correctly to parent."""
        fake_runner = FakeJobRunner(
            session_id="test-session",
            provider_list=[],
            jobs_io_log_dir=None,
        )

        job = mock.MagicMock()
        job.plugin = "shell"
        job_state = mock.MagicMock()
        environ = {"TEST": "value"}
        ui = mock.MagicMock()

        with mock.patch.object(
            UnifiedRunner, "run_job", return_value=mock.MagicMock()
        ) as mock_parent_run_job:
            fake_runner.run_job(
                job, job_state, environ, ui, as_systemd_unit=True
            )

            mock_parent_run_job.assert_called_once_with(
                job, job_state, environ, ui, True
            )
