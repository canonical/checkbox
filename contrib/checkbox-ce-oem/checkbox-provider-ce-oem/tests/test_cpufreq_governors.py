#!/usr/bin/env python3

import unittest
import subprocess
import logging
import sys
from io import StringIO
from unittest.mock import patch, mock_open, Mock, MagicMock

from cpufreq_governors import (
    CPUScalingHandler,
    CPUScalingTest,
    init_logger,
    probe_governor_module,
    stress_cpus,
    stop_stress_cpus,
    context_stress_cpus,
    main,
)


class TestInitLogger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_stdout = sys.stdout
        suppress_text = StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    def setUp(self):
        # Save the original logging configuration
        self.original_log_config = logging.getLogger().handlers

    def tearDown(self):
        # Restore the original logging configuration after each test
        logging.getLogger().handlers = self.original_log_config

    @classmethod
    def tearDownClass(cls):
        sys.stdout = cls.original_stdout
        logging.disable(logging.NOTSET)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_logger_configuration(self, mock_stderr, mock_stdout):
        logger = init_logger()

        # Test if the logger is an instance of logging.Logger
        self.assertIsInstance(logger, logging.Logger)

        # Test if there are three handlers attached to the logger
        # (including the default handler)
        self.assertEqual(len(logger.handlers), 3)

        # Test if the logger level is set to INFO
        self.assertEqual(logger.level, logging.INFO)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    def test_logging_levels(self, mock_stderr, mock_stdout):
        logger = init_logger()

        # Test if the stdout handler has the correct level
        stdout_handler = next(
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and handler.stream == sys.stdout
        )
        self.assertEqual(stdout_handler.level, logging.DEBUG)

        # Test if the stderr handler has the correct level
        stderr_handler = next(
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and handler.stream == sys.stderr
        )
        self.assertEqual(stderr_handler.level, logging.WARNING)


class TestProbeGovernorModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_stdout = sys.stdout
        suppress_text = StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        sys.stdout = cls.original_stdout
        logging.disable(logging.NOTSET)

    @patch("subprocess.check_call")
    @patch("sys.exit")
    @patch("logging.info")
    def test_probe_governor_module_success(
        self, mock_logging_info, mock_sys_exit, mock_subprocess_check_call
    ):
        mock_subprocess_check_call.return_value = None

        probe_governor_module("ondemand")

        mock_logging_info.assert_called_with("Probe module Successfully!")
        # Ensure sys.exit was not called
        mock_sys_exit.assert_not_called()

    @patch("subprocess.check_call")
    @patch("sys.exit")
    @patch("logging.error")
    def test_probe_governor_module_error(
        self, mock_logging_error, mock_sys_exit, mock_subprocess_check_call
    ):
        mock_subprocess_check_call.side_effect = subprocess.CalledProcessError(
            1, "modprobe"
        )

        probe_governor_module("invalid_governor")

        mock_logging_error.assert_called_with(
            "%s governor not supported", "invalid_governor"
        )
        # Ensure sys.exit was called with 1
        mock_sys_exit.assert_called_with(1)


class TestCPUSStress(unittest.TestCase):
    @patch("cpufreq_governors.subprocess.Popen")
    @patch("cpufreq_governors.cpu_count")
    def test_stress_cpus(self, mock_cpu_count, mock_popen):
        mock_cpu_count.return_value = 4  # Simulating 4 CPU cores
        mock_popen_instance = MagicMock()
        mock_popen.return_value = (
            mock_popen_instance  # Mocking the Popen object
        )

        stress_cpus()

        # Assert that the Popen was called 4 times
        self.assertEqual(mock_popen.call_count, 4)
        # Check if the Popen was called with the correct command
        mock_popen.assert_called_with(["dd", "if=/dev/zero", "of=/dev/null"])

    @patch("cpufreq_governors.subprocess.Popen")
    def test_stop_stress_cpus(self, mock_popen):
        # Mocking a list of mock Popen objects
        mock_processes = [
            MagicMock() for _ in range(4)
        ]  # Simulating 4 CPU cores

        stop_stress_cpus(mock_processes)

        for mock_process in mock_processes:
            self.assertEqual(mock_process.terminate.call_count, 1)
            self.assertEqual(mock_process.wait.call_count, 1)

    @patch("cpufreq_governors.stress_cpus")
    def test_context_stress_cpus(self, mock_stress_cpus):
        # Mocking the return value of stress_cpus
        mock_stress_cpus.return_value = [
            MagicMock() for _ in range(4)
        ]  # Simulating 4 CPU cores

        # Using the context manager for context_stress_cpus
        with context_stress_cpus():
            pass

        self.assertEqual(mock_stress_cpus.call_count, 1)


class TestMainFunction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_stdout = sys.stdout
        suppress_text = StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        sys.stdout = cls.original_stdout
        logging.disable(logging.NOTSET)

    @patch("sys.exit")
    def test_debug_logging_enabled(self, mock_exit):
        with patch("sys.argv", ["program_name", "--debug"]):
            logger = init_logger()
            main()
            self.assertEqual(logger.level, logging.DEBUG)

    @patch("sys.exit")
    def test_debug_logging_disabled(self, mock_exit):
        with patch("sys.argv", ["program_name"]):
            logger = init_logger()
            main()
            self.assertEqual(logger.level, logging.INFO)

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_policy_resource_flag_enabled(self, mock_handler, mock_exit):
        with patch("sys.argv", ["program_name", "--policy-resource"]):
            main()
            # fmt: off
            mock_handler.return_value.print_policies_list.\
                assert_called_once_with()
            # fmt: on

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_policy_resource_flag_disabled(self, mock_handler, mock_exit):
        with patch("sys.argv", ["program_name"]):
            main()
            mock_handler.return_value.print_policies_list.assert_not_called()

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingTest")
    def test_driver_detect_flag_enabled(self, mock_test, mock_exit):
        with patch("sys.argv", ["program_name", "--driver-detect"]):
            main()
            mock_test.assert_called_once_with(policy=0)
            mock_test.return_value.test_driver_detect.assert_called_once_with()

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingTest")
    def test_driver_detect_flag_disabled(self, mock_test, mock_exit):
        with patch("sys.argv", ["program_name"]):
            main()
            mock_test.return_value.test_driver_detect.assert_not_called()

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingTest")
    @patch("cpufreq_governors.probe_governor_module")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_valid_governor_has_not_probe(
        self, mock_handler, mock_probe_governor, mock_test, mock_exit
    ):
        mock_test_instance = Mock()
        mock_test.return_value = mock_test_instance
        mock_handler.governors = ["ondemand"]

        with patch(
            "sys.argv", ["program_name", "--governor", "valid_governor1"]
        ):
            main()
            mock_test.assert_called_once_with(policy=0)
            mock_test_instance.print_policy_info.assert_called_once_with()
            mock_probe_governor.assert_called_once_with("valid_governor1")
            mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch("cpufreq_governors.CPUScalingTest")
    @patch("cpufreq_governors.probe_governor_module")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_valid_governor_already_probed(
        self, mock_handler, mock_probe_governor, mock_test, mock_exit
    ):
        mock_test_instance = Mock()
        mock_test.return_value = mock_test_instance
        mock_handler_instance = Mock()
        mock_handler_instance.governors = ["ondemand"]
        mock_handler.return_value = mock_handler_instance

        with patch("sys.argv", ["program_name", "--governor", "ondemand"]):
            main()
            mock_test.assert_called_once_with(policy=0)
            mock_test_instance.print_policy_info.assert_called_once_with()
            mock_probe_governor.assert_not_called()
            mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch("cpufreq_governors.getattr")
    @patch("cpufreq_governors.CPUScalingTest")
    @patch("cpufreq_governors.probe_governor_module")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_given_governor_not_supported(
        self,
        mock_handler,
        mock_probe_governor,
        mock_test,
        mock_getattr,
        mock_exit,
    ):
        mock_test_instance = Mock()
        mock_test.return_value = mock_test_instance
        mock_handler_instance = Mock()
        mock_handler_instance.governors = ["ondemand"]
        mock_handler.return_value = mock_handler_instance
        mock_getattr.side_effect = AttributeError("AttributeError message")

        with patch("sys.argv", ["program_name", "--governor", "not_support"]):
            main()
            mock_test.assert_called_once_with(policy=0)
            mock_test_instance.print_policy_info.assert_called_once_with()
            mock_probe_governor.assert_called_once_with("not_support")
            mock_exit.assert_called_once_with(1)

    @patch("sys.exit")
    @patch("cpufreq_governors.getattr")
    @patch("cpufreq_governors.CPUScalingTest")
    @patch("cpufreq_governors.probe_governor_module")
    @patch("cpufreq_governors.CPUScalingHandler")
    def test_getattr_return_false(
        self,
        mock_handler,
        mock_probe_governor,
        mock_test,
        mock_getattr,
        mock_exit,
    ):
        mock_test_instance = Mock()
        mock_test.return_value = mock_test_instance
        mock_handler_instance = Mock()
        mock_handler_instance.governors = ["ondemand"]
        mock_handler.return_value = mock_handler_instance
        mock_callable = MagicMock(return_value=False)
        mock_getattr.return_value = mock_callable

        with patch("sys.argv", ["program_name", "--governor", "not_support"]):
            main()
            mock_test.assert_called_once_with(policy=0)
            mock_test_instance.print_policy_info.assert_called_once_with()
            mock_probe_governor.assert_called_once_with("not_support")
            mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
