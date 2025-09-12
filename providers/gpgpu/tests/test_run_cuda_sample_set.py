#!/usr/bin/env python3
"""Tests for the run_cuda_sample_set.py script.

Copyright 2025 Canonical Ltd.

Written by:
  Antone Lassagne <antoine.lassagne@canonical.com>

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

import unittest
import os
from unittest import mock
from pathlib import Path
import subprocess
from unittest.mock import patch
import logging

import run_cuda_sample_set

global clone_counter
clone_counter = 0


def dummy_clone(orig_dir, test_set):
    global clone_counter

    def wrapper(*args, **kwargs) -> subprocess.CompletedProcess:
        global clone_counter
        if clone_counter > 0:
            return subprocess.CompletedProcess("", 0)
        clone_counter = clone_counter + 1
        # Create a temporary directory to simulate the workspace
        test_set_dir_to_keep = (
            orig_dir / test_set / "Samples" / "5_Domain_Specific"
        )
        test_set_dir_to_keep_2 = orig_dir / test_set / "Samples" / "3_Dummy"
        test_set_dir_to_keep_5 = (
            orig_dir
            / test_set
            / "Samples"
            / "8_Platform_Specific"
            / "Tegra"
            / "cudaNvSciBufMultiplanar"
        )

        test_set_dir_to_keep_7 = (
            orig_dir / test_set / "Samples" / "7_libNVVM" / "ptxgen"
        )

        test_set_dir_to_keep_4 = (
            orig_dir
            / test_set
            / "Samples"
            / "2_Concepts_and_Techniques"
            / "EGLStream_CUDA_Interop"
        )
        test_set_dir_to_keep_4_2 = (
            orig_dir
            / test_set
            / "build"
            / "Samples"
            / "2_Concepts_and_Techniques"
            / "EGLStream_CUDA_Interop"
        )

        test_set_dir_to_keep_3 = orig_dir / test_set / "Samples" / "Common"
        test_set_dir_to_trash = orig_dir / test_set / "Samples" / "0_Utilities"

        test_set_dir_to_keep.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_2.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_3.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_5.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_7.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_4.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_keep_4_2.mkdir(parents=True, exist_ok=True)
        test_set_dir_to_trash.mkdir(parents=True, exist_ok=True)

        with open(str(Path(test_set_dir_to_keep_4 / "truc.yuv")), "w") as file:
            file.write("dummydum")

        with open(str(Path(test_set_dir_to_keep_5 / "truc.yuv")), "w") as file:
            file.write("dummydum")

        with open(
            str(Path(orig_dir / test_set / "CMakeLists.txt")), "w"
        ) as file:
            file.write("dummydum")

        return subprocess.CompletedProcess("", 0)

    return wrapper


class TestCudaSamples(unittest.TestCase):

    @mock.patch("subprocess.run")
    @mock.patch("pathlib.Path.write_text")
    @mock.patch("run_cuda_sample_set.remove_add_subdirectory_line")
    def test_clone_and_build(
        self,
        mock_radd_sub_line,
        mock_write_text,
        mock_subprocess_run,
    ):
        global clone_counter
        # Set environment variables
        test_set = "5"
        cuda_samples_version = 12.8
        orig_dir = Path(".")
        mock_subprocess_run.side_effect = dummy_clone(orig_dir, test_set)

        # what if there is the wrong folder already
        path = orig_dir / test_set
        path.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(FileExistsError):
            run_cuda_sample_set.clone_and_build(
                orig_dir, test_set, cuda_samples_version
            )

        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        run_cuda_sample_set.clone_and_build(
            orig_dir, test_set, cuda_samples_version
        )
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        run_cuda_sample_set.cleanup_temporary_files(".", str(0))

        test_set = "2"
        clone_counter = 0
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        mock_subprocess_run.side_effect = dummy_clone(orig_dir, test_set)
        run_cuda_sample_set.clone_and_build(
            orig_dir, test_set, cuda_samples_version
        )
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))

        test_set = "8"
        clone_counter = 0
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        mock_subprocess_run.side_effect = dummy_clone(orig_dir, test_set)
        run_cuda_sample_set.clone_and_build(
            orig_dir, test_set, cuda_samples_version
        )
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))

        test_set = "7"
        clone_counter = 0
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))
        mock_subprocess_run.side_effect = dummy_clone(orig_dir, test_set)
        run_cuda_sample_set.clone_and_build(
            orig_dir, test_set, cuda_samples_version
        )
        run_cuda_sample_set.cleanup_temporary_files(".", str(test_set))

    def test_remove_add_subdirectory_line(self):
        filepath = "test.txt"
        text = "hello"
        with open(filepath, "w") as file:
            file.write("first line\n")
            file.write("add_subdirectory(" + text + ")\n")
            file.write("add_subdirectory(hellooo)\n")
            file.write("third line\n")

        run_cuda_sample_set.remove_add_subdirectory_line(filepath, text)

        with open(filepath, "r") as f:
            lines = f.readlines()

        self.assertEqual(lines[0], "first line\n")
        self.assertEqual(lines[1], "add_subdirectory(hellooo)\n")
        self.assertEqual(lines[2], "third line\n")
        self.assertEqual(len(lines), 3)

    @mock.patch("pathlib.Path.mkdir")
    @mock.patch("shutil.copy")
    @mock.patch("os.chmod")
    def test_copy_and_set_permissions(self, mock_mkdir, mock_copy, mock_chmod):
        with open("test.txt", "w") as file:
            file.write("first line\n")
        run_cuda_sample_set.copy_and_set_permissions(".", ".", ".txt")
        os.remove("test.txt")

    @mock.patch("subprocess.run", return_value=True)
    def test_run_test(self, mock_run):
        # Create a temporary directory to simulate the workspace
        orig_dir = Path(".")
        exe_dir = (
            orig_dir
            / "3"
            / "build"
            / "Samples"
            / "5_Domain_Specific"
            / "truc"
            / "bin"
        )
        exe_dir.mkdir(parents=True, exist_ok=True)

        # Create the dummy script and write the echo command to it
        with open(str(Path(exe_dir / "3.sh")), "w") as file:
            file.write("#!/bin/bash\n")
            file.write("echo hello world 1\n")

        with open(str(Path(exe_dir / "test2")), "w") as file:
            file.write("#!/bin/bash\n")
            file.write("echo hello world 2\n")

        with open(str(Path(exe_dir / "test1")), "w") as file:
            file.write("#!/bin/bash\n")
            file.write("echo hello world 3\n")
        with open(str(Path(exe_dir / "testnope")), "w") as file:
            file.write("#!/bin/bash\n")

        os.chmod(str(Path(exe_dir / "3.sh")), 0o755)
        os.chmod(str(Path(exe_dir / "test2")), 0o755)
        os.chmod(str(Path(exe_dir / "test1")), 0o755)

        total, skipped = run_cuda_sample_set.run_tests("./", "3", ["test1"])
        self.assertEqual(total, 3)
        self.assertEqual(skipped, 1)
        run_cuda_sample_set.cleanup_temporary_files("./", str(3))

    @mock.patch(
        "run_cuda_sample_set.parse_args",
        return_value=run_cuda_sample_set.argparse.Namespace(
            no_clone=False,
            keep_cache=False,
            cuda_ignore_tensorcore="1",
            cuda_multigpu="1",
            cuda_ignore_tests="test1 test2",
            test_set="2",
            cuda_samples_version="12.8",
            missing_files=[(".", ".", ".txt")],
            log_level=logging.INFO,
        ),
    )
    @mock.patch(
        "run_cuda_sample_set.clone_and_build",
        side_effect=FileExistsError("File exist patched."),
    )
    @mock.patch(
        "run_cuda_sample_set.run_tests",
        side_effect=subprocess.CalledProcessError(
            "File exist patched.", cmd=""
        ),
    )
    def test_main(self, mock_run, mock_clone, mock_args):
        with self.assertRaises(FileExistsError):
            run_cuda_sample_set.main()
        mock_clone.side_effect = None
        with self.assertRaises(subprocess.CalledProcessError):
            run_cuda_sample_set.main()

        mock_run.side_effect = None
        run_cuda_sample_set.main()

    @patch("run_cuda_sample_set.argparse")
    def test_parse_args(self, argparse_mock):
        run_cuda_sample_set.parse_args()
