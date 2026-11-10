import resource
import unittest
from unittest.mock import DEFAULT, patch

import cpufreq_test


class TestFileDescriptorLimit(unittest.TestCase):
    def setUp(self):
        self.test = cpufreq_test.CpuFreqTest.__new__(cpufreq_test.CpuFreqTest)
        self.fds = patch(
            "cpufreq_test.listdir", return_value=["0", "1", "2", "3"]
        )
        self.fds.start()
        self.addCleanup(self.fds.stop)
        setter = patch("cpufreq_test.resource.setrlimit")
        self.setrlimit = setter.start()
        self.addCleanup(setter.stop)

    @patch("cpufreq_test.resource.getrlimit", return_value=(1024, 4096))
    def test_warns_for_dual_socket_576_core_server(self, getrlimit):
        with self.assertLogs(level="WARNING") as logs:
            self.assertTrue(self.test._ensure_fd_limit(576))

        message = logs.output[0]
        self.assertIn("576 workers", message)
        self.assertIn("1159 file descriptors", message)
        self.assertIn("limit is 1024", message)
        self.assertIn("Raising RLIMIT_NOFILE to 2183", message)
        getrlimit.assert_called_once_with(resource.RLIMIT_NOFILE)
        self.setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (2183, 4096)
        )

    @patch("cpufreq_test.logging.warning")
    @patch("cpufreq_test.resource.getrlimit")
    def test_no_warning_when_limit_is_sufficient(self, getrlimit, warning):
        for limit in (2183, 4096, resource.RLIM_INFINITY):
            with self.subTest(limit=limit):
                getrlimit.return_value = (limit, resource.RLIM_INFINITY)
                self.assertTrue(self.test._ensure_fd_limit(576))
                warning.assert_not_called()
                self.setrlimit.assert_not_called()

    @patch("cpufreq_test.resource.getrlimit", return_value=(1024, 4096))
    def test_includes_existing_open_descriptors(self, getrlimit):
        with patch("cpufreq_test.listdir", return_value=list(range(21))):
            with self.assertLogs(level="WARNING") as logs:
                self.test._ensure_fd_limit(576)

        self.assertIn("1176 file descriptors", logs.output[0])
        self.setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (2200, 4096)
        )

    @patch("cpufreq_test.resource.getrlimit", return_value=(1024, 2048))
    def test_caps_increase_at_hard_limit(self, getrlimit):
        with self.assertLogs(level="WARNING") as logs:
            self.test._ensure_fd_limit(576)
        self.setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (2048, 2048)
        )
        self.assertIn("hard limit 2048", logs.output[0])

    @patch("cpufreq_test.resource.getrlimit")
    def test_unlimited_hard_limit(self, getrlimit):
        getrlimit.return_value = (1024, resource.RLIM_INFINITY)
        with self.assertLogs(level="WARNING"):
            self.test._ensure_fd_limit(576)
        self.setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (2183, resource.RLIM_INFINITY)
        )

    @patch("cpufreq_test.resource.getrlimit")
    def test_rejects_insufficient_hard_limit(self, getrlimit):
        for soft_limit in (512, 1024):
            with self.subTest(soft_limit=soft_limit):
                getrlimit.return_value = (soft_limit, 1024)
                with self.assertLogs(level="ERROR") as logs:
                    self.assertFalse(self.test._ensure_fd_limit(576))
                self.assertIn(
                    "below the estimated required total of 1159",
                    logs.output[-1],
                )
                self.setrlimit.assert_not_called()

    @patch("cpufreq_test.resource.getrlimit", return_value=(1024, 4096))
    def test_logs_and_propagates_setrlimit_failure(self, getrlimit):
        for error in (OSError("permission denied"), ValueError("invalid")):
            with self.subTest(error=error):
                self.setrlimit.side_effect = error
                with self.assertLogs(level="ERROR") as logs:
                    with self.assertRaises(type(error)):
                        self.test._ensure_fd_limit(576)
                self.assertIn(
                    "Unable to raise the soft file descriptor limit",
                    logs.output[0],
                )

    @patch("cpufreq_test.resource.getrlimit", return_value=(1024, 4096))
    @patch.object(cpufreq_test.CpuFreqTest, "_get_cores")
    @patch.object(cpufreq_test.CpuFreqTest, "disable_thread_siblings")
    @patch.object(cpufreq_test.CpuFreqTest, "_write_sysfs")
    @patch.object(cpufreq_test.CpuFreqTest, "set_governors")
    @patch.object(cpufreq_test.CpuFreqTest, "spawn_core_test")
    def test_limit_failure_precedes_cpu_changes(
        self, spawn, governors, write_sysfs, disable_siblings, cores, getrlimit
    ):
        cores.return_value = list(range(1152))
        self.setrlimit.side_effect = OSError("permission denied")

        with self.assertLogs(level="ERROR"):
            with self.assertRaises(OSError):
                self.test.execute_test()

        cores.assert_called_once_with("online")
        self.setrlimit.assert_called_once_with(
            resource.RLIMIT_NOFILE, (3335, 4096)
        )
        disable_siblings.assert_not_called()
        write_sysfs.assert_not_called()
        governors.assert_not_called()
        spawn.assert_not_called()

    @patch("cpufreq_test.resource.getrlimit", return_value=(38, 4096))
    @patch.object(cpufreq_test.CpuFreqTest, "_get_cores")
    def test_successful_limit_increase_allows_test_to_run(self, cores, limits):
        cores.return_value = list(range(16))
        self.test.scaling_driver = "amd-pstate"
        self.test.driver_types = ()
        self.test.fail_count = 0
        self.test._CpuFreqTest__proc_list = []

        def check_limit_before_cpu_changes():
            self.setrlimit.assert_called_once_with(
                resource.RLIMIT_NOFILE, (1063, 4096)
            )

        with patch.multiple(
            cpufreq_test.CpuFreqTest,
            disable_thread_siblings=DEFAULT,
            set_governors=DEFAULT,
            spawn_core_test=DEFAULT,
            reset=DEFAULT,
            _process_results=DEFAULT,
        ) as mocks, patch("builtins.print"):
            mocks["disable_thread_siblings"].side_effect = (
                check_limit_before_cpu_changes
            )
            mocks["_process_results"].return_value = {}
            with self.assertLogs(level="WARNING"):
                self.assertEqual(self.test.execute_test(), 0)

            mocks["disable_thread_siblings"].assert_called_once_with()
            mocks["set_governors"].assert_called_once_with("performance")
            mocks["spawn_core_test"].assert_called_once_with()
            mocks["reset"].assert_called_once_with()

    @patch("cpufreq_test.resource.getrlimit", return_value=(38, 38))
    @patch.object(cpufreq_test.CpuFreqTest, "_get_cores")
    @patch.object(cpufreq_test.CpuFreqTest, "disable_thread_siblings")
    @patch.object(cpufreq_test.CpuFreqTest, "_write_sysfs")
    @patch.object(cpufreq_test.CpuFreqTest, "set_governors")
    @patch.object(cpufreq_test.CpuFreqTest, "spawn_core_test")
    def test_insufficient_hard_limit_exits_before_cpu_changes(
        self, spawn, governors, write_sysfs, disable_siblings, cores, getrlimit
    ):
        cores.return_value = list(range(16))
        with self.assertLogs(level="ERROR") as logs:
            self.assertEqual(self.test.execute_test(), 1)

        self.assertIn("required total of 39", logs.output[0])
        self.assertIn("refusing to start", logs.output[0])
        self.setrlimit.assert_not_called()
        disable_siblings.assert_not_called()
        write_sysfs.assert_not_called()
        governors.assert_not_called()
        spawn.assert_not_called()
