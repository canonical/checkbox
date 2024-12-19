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

from unittest import TestCase
from unittest.mock import MagicMock, patch

from gpu_passthrough import (
    main,
    parse_args,
    run_gpu_test,
    test_lxd_gpu,
    test_lxdvm_gpu,
)


@patch("gpu_passthrough.logging")
class TestMain(TestCase):
    @patch("time.time", side_effect=[0, 1])
    def test_run_gpu_test_success(self, time_mock, logging_mock):
        instance = MagicMock()
        try:
            run_gpu_test(instance, "test", run_count=1, threshold_sec=2)
        except SystemExit:
            self.fail("run_gpu_test raised SystemExit")

    @patch("time.time", side_effect=[0, 2])
    def test_run_gpu_test_failure(self, time_mock, logging_mock):
        instance = MagicMock()
        with self.assertRaises(SystemExit):
            run_gpu_test(instance, "test", run_count=1, threshold_sec=1)

    @patch("gpu_passthrough.run_gpu_test")
    @patch("gpu_passthrough.LXD")
    def test_test_lxd_gpu(self, lxd_mock, run_mock, logging_mock):
        args = MagicMock(vendor="nvidia")
        test_lxd_gpu(args)

    @patch("gpu_passthrough.run_gpu_test")
    @patch("gpu_passthrough.LXDVM")
    def test_test_lxdvm_gpu(self, lxdvm_mock, run_mock, logging_mock):
        args = MagicMock(vendor="nvidia")
        test_lxdvm_gpu(args)

    @patch("gpu_passthrough.argparse")
    def test_parse_args(self, argparse_mock, logging_mock):
        parse_args()

    @patch("gpu_passthrough.parse_args")
    def test_main(self, parse_args_mock, logging_mock):
        main()
