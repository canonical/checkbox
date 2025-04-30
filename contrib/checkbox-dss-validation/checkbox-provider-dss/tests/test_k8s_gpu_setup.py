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

import json
import os
import subprocess
import textwrap
import unittest
from unittest import mock

from checkbox_support.helpers.timeout import mock_timeout
from checkbox_support.helpers.retry import mock_retry

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


@mock_retry()
@mock_timeout()
class TestInstallIntelGpuPlugin(unittest.TestCase):
    version = k8s_gpu_setup.DEFAULT_INTEL_PLUGIN_VERSION
    repo = (
        "https://github.com/intel/"
        "intel-device-plugins-for-kubernetes/deployments"
    )
    apply = "kubectl apply -k "

    @mock.patch("subprocess.check_call")
    def test_kustomizes_and_checks_rollout(self, mock_call):
        mock_call.__name__ = "subprocess.check_call"
        k8s_gpu_setup.install_intel_gpu_plugin(self.version)

        urls = [
            f"{self.repo}/nfd?ref={self.version}",
            f"{self.repo}/nfd/overlays/node-feature-rules?ref={self.version}",
            (
                f"{self.repo}/gpu_plugin/overlays/"
                f"nfd_labeled_nodes?ref={self.version}"
            ),
        ]
        calls = [mock.call(f"{self.apply} {url}".split()) for url in urls]

        rollout = "kubectl -n default rollout status ds/intel-gpu-plugin"
        calls.append(mock.call(rollout.split()))

        with self.subTest("number of calls"):
            self.assertEqual(len(mock_call.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_call.assert_has_calls(calls)


@mock_timeout()
@mock.patch("subprocess.check_output")
class TestDetectIfMicrok8s(unittest.TestCase):
    def test_microk8s_is_running(self, mocked_call):
        mocked_call.return_value = textwrap.dedent(
            """\
            microk8s is running
            high-availability: no
              datastore master nodes: 127.0.0.1:19001
              datastore standby nodes: none
            addons:
              enabled:
                <snip>
            """
        )
        result = k8s_gpu_setup.detect_if_microk8s()

        with self.subTest("mock was called"):
            mocked_call.assert_called_once_with(
                ["microk8s", "status"], text=True
            )

        with self.subTest("result is True"):
            self.assertTrue(result)

    def test_microk8s_is_not_running(self, mocked_call):
        mocked_call.return_value = (
            "microk8s is not running, try microk8s start"
        )
        result = k8s_gpu_setup.detect_if_microk8s()

        with self.subTest("result is False"):
            self.assertFalse(result)

    def test_called_process_error(self, mocked_call):
        mocked_call.side_effect = subprocess.CalledProcessError(2, "command")
        result = k8s_gpu_setup.detect_if_microk8s()
        self.assertFalse(result)


@mock_retry()
@mock_timeout()
@mock.patch("time.sleep", new=lambda x: None)
class TestInstallNvidialGpuOperator(unittest.TestCase):
    version = k8s_gpu_setup.DEFAULT_NVIDIA_OPERATOR_VERSION
    namespace = "gpu-operator-resources"

    def helm_repo_calls(self):
        repo_url = "https://helm.ngc.nvidia.com/nvidia"
        calls = [
            mock.call(f"helm repo add nvidia {repo_url}".split(), check=True),
            mock.call("helm repo update".split(), check=True),
        ]
        return calls

    def rollout_call(self):
        return [
            mock.call(
                (
                    f"kubectl -n {self.namespace} "
                    "rollout status ds/nvidia-device-plugin-daemonset"
                ).split(),
                check=True,
            ),
            mock.call(
                (
                    f"kubectl -n {self.namespace} "
                    "rollout status ds/nvidia-operator-validator"
                ).split(),
                check=True,
            ),
        ]

    @mock.patch("subprocess.run")
    @mock.patch("k8s_gpu_setup.detect_if_microk8s", lambda: False)
    def test_microk8s_not_detected(self, mock_call):
        mock_call.__name__ = "subprocess.check_call"
        k8s_gpu_setup.install_nvidia_gpu_operator(self.version)

        helm_install = (
            "helm install --wait --generate-name --create-namespace "
            f"-n {self.namespace} nvidia/gpu-operator "
            f"--version={self.version}"
        )
        calls = [
            *self.helm_repo_calls(),
            mock.call(helm_install.split(), input=None, check=True),
            *self.rollout_call(),
        ]

        with self.subTest("number of calls"):
            self.assertEqual(len(mock_call.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_call.assert_has_calls(calls)

    @mock.patch("subprocess.run")
    @mock.patch("k8s_gpu_setup.detect_if_microk8s")
    def test_timed_out_detecting_microk8s(self, mock_detect, mock_call):
        mock_call.__name__ = "subprocess.check_call"
        exception = TimeoutError()
        mock_detect.side_effect = exception
        with self.assertRaises(TimeoutError) as caught:
            k8s_gpu_setup.install_nvidia_gpu_operator(self.version)
        self.assertEqual(caught.exception, exception)

    @mock.patch("subprocess.run")
    @mock.patch("k8s_gpu_setup.detect_if_microk8s", lambda: True)
    def test_microk8s_detected(self, mock_call):
        mock_call.__name__ = "subprocess.check_call"
        k8s_gpu_setup.install_nvidia_gpu_operator(self.version)

        helm_install = (
            "helm install --wait --generate-name --create-namespace "
            f"-n {self.namespace} nvidia/gpu-operator "
            f"--version={self.version} -f -"
        )

        containerd_config_path = (
            "/var/snap/microk8s/current/args/containerd-template.toml"
        )
        containerd_socket_path = (
            "/var/snap/microk8s/common/run/containerd.sock"
        )
        helm_config = {
            "toolkit": {
                "env": [
                    {
                        "name": "CONTAINERD_CONFIG",
                        "value": containerd_config_path,
                    },
                    {
                        "name": "CONTAINERD_SOCKET",
                        "value": containerd_socket_path,
                    },
                ]
            }
        }
        calls = [
            *self.helm_repo_calls(),
            mock.call(
                helm_install.split(),
                input=json.dumps(helm_config).encode(),
                check=True,
            ),
            *self.rollout_call(),
        ]

        with self.subTest("number of calls"):
            self.assertEqual(len(mock_call.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_call.assert_has_calls(calls)
