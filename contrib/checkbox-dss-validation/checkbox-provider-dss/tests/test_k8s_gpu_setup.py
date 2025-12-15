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

import contextlib
import itertools
import os
import json
import tempfile
import shutil
import unittest
from unittest import mock

import yaml

from checkbox_support.helpers.timeout import mock_timeout
from checkbox_support.helpers.retry import mock_retry

import k8s_gpu_setup


DEFAULT_NVIDIA_OPERATOR_VERSION = "v24.6.2"
DEFAULT_INTEL_PLUGIN_VERSION = "v0.30.0"


@mock_retry()
@mock_timeout()
@mock.patch("time.sleep", new=lambda x: None)
class TestInstallIntelGpuPlugin(unittest.TestCase):
    version = DEFAULT_INTEL_PLUGIN_VERSION
    repo = "https://github.com/intel/" "intel-device-plugins-for-kubernetes/deployments"
    apply = "kubectl apply -k "

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir_path)

    @contextlib.contextmanager
    def temp_dir_for_testing(self):
        yield self.temp_dir_path

    @mock.patch("tempfile.TemporaryDirectory")
    @mock.patch("subprocess.run")
    def test_kustomizes_and_checks_rollout(self, mock_run, mock_tempdir):
        mock_run.__name__ = "subprocess.run"
        mock_tempdir.return_value = self.temp_dir_for_testing()

        k8s_gpu_setup.setup_intel_gpu_plugin(self.version, False)

        urls = [
            f"{self.repo}/nfd?ref={self.version}",
            f"{self.repo}/nfd/overlays/node-feature-rules?ref={self.version}",
            self.temp_dir_path,
        ]
        calls = [mock.call(f"{self.apply} {url}".split(), check=True) for url in urls]

        gpu_plugin_url = (
            f"{self.repo}/gpu_plugin/overlays/" f"nfd_labeled_nodes?ref={self.version}"
        )
        with (
            open(os.path.join(self.temp_dir_path, "kustomization.yaml")) as f,
            self.subTest("gpu plugin patch"),
        ):
            kustomization = yaml.safe_load(f)
            with self.subTest("resources url"):
                self.assertListEqual(kustomization["resources"], [gpu_plugin_url])

            with self.subTest("num patches"):
                patches = kustomization["patches"]
                self.assertEqual(len(patches), 1)

            with self.subTest("patch content"):
                patch_value = yaml.safe_load(patches[0]["patch"])
                self.assertEqual(
                    patch_value,
                    k8s_gpu_setup.INTEL_GPU_PLUGIN_KUSTOMIZATION_PATCH,
                )

        for rollout in [
            "kubectl -n node-feature-discovery rollout status ds/nfd-worker",
            "kubectl -n default rollout status ds/intel-gpu-plugin",
        ]:
            calls.append(mock.call(rollout.split(), check=True))

        with self.subTest("number of calls"):
            self.assertEqual(len(mock_run.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_run.assert_has_calls(calls)


@mock_retry()
@mock_timeout()
@mock.patch("time.sleep", new=lambda x: None)
class TestInstallNvidialGpuOperator(unittest.TestCase):
    version = DEFAULT_NVIDIA_OPERATOR_VERSION
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
    def test_without_microk8s(self, mock_run):
        mock_run.__name__ = "subprocess.check_call"
        k8s_gpu_setup.setup_nvidia_gpu_operator(self.version, False)

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
            self.assertEqual(len(mock_run.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_run.assert_has_calls(calls)

    @mock.patch("subprocess.run")
    def test_for_microk8s(self, mock_run):
        mock_run.__name__ = "subprocess.check_call"
        k8s_gpu_setup.setup_nvidia_gpu_operator(self.version, True)

        helm_install = (
            "helm install --wait --generate-name --create-namespace "
            f"-n {self.namespace} nvidia/gpu-operator "
            f"--version={self.version} -f -"
        )

        containerd_config_path = (
            "/var/snap/microk8s/current/args/containerd-template.toml"
        )
        containerd_socket_path = "/var/snap/microk8s/common/run/containerd.sock"
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
            self.assertEqual(len(mock_run.mock_calls), len(calls))
        with self.subTest("order of calls"):
            mock_run.assert_has_calls(calls)


@mock.patch("k8s_gpu_setup.setup_intel_gpu_plugin")
@mock.patch("k8s_gpu_setup.setup_nvidia_gpu_operator")
class TestMainCli(unittest.TestCase):
    def test_vendor_must_be_intel_or_nvidia(self, nvidia_setup, intel_setup):
        version = "version"
        for vendor, microk8s in itertools.product(["intel", "nvidia"], [True, False]):
            args = [vendor, version]
            if microk8s:
                args.append("--microk8s")

            with self.subTest(f"{vendor}-{microk8s} must pass"):
                k8s_gpu_setup.main(args)
                if vendor == "nvidia":
                    nvidia_setup.assert_called_with(version, microk8s)
                elif vendor == "intel":
                    intel_setup.assert_called_with(version, microk8s)
                else:  # pragma: no cover
                    self.fail(f"unhandled vendor {vendor}")

        unsupported_vendor = "amd"  # for example
        for microk8s in [True, False]:
            args = [unsupported_vendor, version]
            if microk8s:
                args.append("--microk8s")

            with self.subTest(f"{unsupported_vendor}-{microk8s} must fail"):
                with self.assertRaises(SystemExit) as caught:
                    k8s_gpu_setup.main(args)
                self.assertEquals(caught.exception.code, 2)
