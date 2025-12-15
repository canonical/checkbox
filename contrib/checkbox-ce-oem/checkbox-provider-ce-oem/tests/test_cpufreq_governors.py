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
        mock_popen.return_value = mock_popen_instance  # Mocking the Popen object

        stress_cpus()

        # Assert that the Popen was called 4 times
        self.assertEqual(mock_popen.call_count, 4)
        # Check if the Popen was called with the correct command
        mock_popen.assert_called_with(["dd", "if=/dev/zero", "of=/dev/null"])

    @patch("cpufreq_governors.subprocess.Popen")
    def test_stop_stress_cpus(self, mock_popen):
        # Mocking a list of mock Popen objects
        mock_processes = [MagicMock() for _ in range(4)]  # Simulating 4 CPU cores

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
