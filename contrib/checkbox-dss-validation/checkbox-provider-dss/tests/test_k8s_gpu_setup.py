#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
#
"""Tests for `k8s_gpu_setup.py`"""

import os
import unittest
from unittest import mock

from checkbox_support.helpers.timeout import mock_timeout

import k8s_gpu_setup


@mock_timeout()
class TestMain(unittest.TestCase):
    @mock.patch("k8s_gpu_setup.install_intel_gpu_plugin")
    def test_uses_default_version_for_intel_gpu_plugin(self, mocked):
        k8s_gpu_setup.main(["intel"])
        mocked.assert_called_once_with(
            k8s_gpu_setup.DEFAULT_INTEL_PLUGIN_VERSION
        )

    @mock.patch("k8s_gpu_setup.install_intel_gpu_plugin")
    def test_uses_given_version_for_intel_gpu_plugin(self, mocked):
        version = "v0.30.0"
        k8s_gpu_setup.main(["intel", "--version", version])
        mocked.assert_called_once_with(version)

    @mock.patch("k8s_gpu_setup.install_intel_gpu_plugin")
    def test_uses_version_from_env_for_intel_gpu_plugin(self, mocked):
        version = "Total Valid Version"
        os.environ["INTEL_GPU_PLUGIN_VERSION"] = version
        k8s_gpu_setup.main(["intel", "--version", version])
        mocked.assert_called_once_with(version)

    @mock.patch("k8s_gpu_setup.install_nvidia_gpu_operator")
    def test_uses_default_version_for_nvidia_gpu_operator(self, mocked):
        k8s_gpu_setup.main(["nvidia"])
        mocked.assert_called_once_with(
            k8s_gpu_setup.DEFAULT_NVIDIA_OPERATOR_VERSION
        )

    @mock.patch("k8s_gpu_setup.install_nvidia_gpu_operator")
    def test_uses_given_version_for_nvidia_gpu_operator(self, mocked):
        version = "v25.3.9"
        k8s_gpu_setup.main(["nvidia", "--version", version])
        mocked.assert_called_once_with(version)

    @mock.patch("k8s_gpu_setup.install_nvidia_gpu_operator")
    def test_uses_version_from_env_for_nvidia_gpu_operator(self, mocked):
        version = "Total Valid Version"
        os.environ["NVIDIA_GPU_OPERATOR_VERSION"] = version
        k8s_gpu_setup.main(["nvidia", "--version", version])
        mocked.assert_called_once_with(version)
