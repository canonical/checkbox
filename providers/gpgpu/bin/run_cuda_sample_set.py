#!/usr/bin/env python3
"""Script to build and run cuda samples, to test cuda features on nvidia gpus.

Copyright (C) 2025 Canonical Ltd.

Authors
  Antone Lassagne <antone.lassagne@canonical.com>

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

import argparse

import os

import shutil

import subprocess
import sys

from pathlib import Path


def exit_trap(orig_dir, test_set):
    test_set_dir = Path(orig_dir) / test_set
    print("Cleaning up", test_set_dir)
    shutil.rmtree(str(test_set_dir), ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a set of CUDA tests with customizable configurations."
    )

    # Argument for specifying the test set index
    parser.add_argument(
        "--test-set",
        type=int,
        choices=range(9),
        help=""""
        "Index of the test set (0 to 8).
        Options are:
            0 --> Introduction
            1 --> Utilities
            2 --> Concepts_and_Techniques
            3 --> CUDA_Features
            4 --> CUDA_Libraries
            5 --> Domain_Specific
            6 --> Performance
            7 --> libNVVM
            8 --> Platform_Specific
            """,
    )

    # Optional arguments for environment variables
    parser.add_argument(
        "--cuda_samples_version",
        default=os.getenv("CUDA_SAMPLES_VERSION", "12.8"),
        help="CUDA samples version (default: 12.8).",
    )
    parser.add_argument(
        "--cuda_ignore_tensorcore",
        default=os.getenv("CUDA_IGNORE_TENSORCORE", "0"),
        choices=["0", "1"],
        help="Ignore TensorCores if the machine does not have them.",
    )
    parser.add_argument(
        "--cuda_multigpu",
        default=os.getenv("CUDA_MULTIGPU", "0"),
        choices=["0", "1"],
        help="Enable if the machine has multiple NVIDIA GPUs.",
    )
    parser.add_argument(
        "--clone",
        default=os.getenv("CLONE", "1"),
        choices=["0", "1"],
        help="[DEBUG] Clone - default is 1",
    )
    parser.add_argument(
        "--keep_cache",
        default=os.getenv("KEEP_CACHE", "0"),
        choices=["0", "1"],
        help="[DEBUG] Keep cache - default is 0",
    )

    parser.add_argument(
        "--cuda_ignore_tests",
        default=os.getenv("CUDA_IGNORE_TESTS", ""),
        help="Space-separated list of tests to ignore.",
    )

    # Parse the arguments
    return parser.parse_args()


def print_colored(color: str, text: str):
    color_map = {
        "green": "\033[32m",
        "red": "\033[31m",
    }
    color_code = color_map.get(color, "")
    reset_code = "\033[0m"
    print(color_code + text + reset_code)


def write_first_line_to_file(file_path: str, line: str):
    with open(str(file_path), "r") as f:
        lines = f.readlines()

    lines.insert(0, line + "\n")  # you can replace zero with any line number.
    with open(str(file_path), "w") as f:
        f.writelines(lines)


def remove_add_subdirectory_line(cmake_file, dir_name):

    dir_name = os.path.basename(str(dir_name))
    cmake_file_path = Path(cmake_file)

    # Read the current content of the CMakeLists.txt
    with cmake_file_path.open("r") as file:
        lines = file.readlines()

    # Write back to the CMakeLists.txt excluding lines with the specified
    # add_subdirectory
    with cmake_file_path.open("w") as file:
        for line in lines:
            if "add_subdirectory(" + dir_name + ")" not in line:
                file.write(line)


def copy_and_set_permissions(src, dst, file_extension):
    os.makedirs(dst, exist_ok=True)

    # Copy the files with the given extension
    for filename in os.listdir(src):
        if filename.endswith(file_extension):
            shutil.copy(os.path.join(src, filename), dst)

            # Set file permissions to remove execute bit
            file_path = os.path.join(dst, filename)
            os.chmod(file_path, 0o644)


# Function to clone the repository and build the correct subfolder
def clone_and_build(orig_dir, test_set, cuda_samples_version):
    test_set_dir = Path(orig_dir) / test_set
    if test_set_dir.exists():
        raise FileExistsError(
            "Error: folder " + str(test_set_dir) + " exists."
        )

    print(
        "Cloning CUDA Samples v"
        + str(cuda_samples_version)
        + ". Change the version"
        " in the manifest if you need another one."
    )
    subprocess.run(
        [
            "git",
            "clone",
            "-b",
            "v" + str(cuda_samples_version),
            "--single-branch",
            "https://github.com/NVIDIA/cuda-samples.git",
            str(test_set_dir),
        ],
        check=True,
    )

    cmake_file = test_set_dir / "CMakeLists.txt"
    write_first_line_to_file(cmake_file, 'set(EXECUTABLE_OUTPUT_PATH "bin")')

    # Remove unnecessary folders
    samples_dir = test_set_dir / "Samples"
    for folder in samples_dir.glob("[0-9]_*/"):
        folder_number = folder.name.split("_")[0]
        if folder_number != test_set:
            shutil.rmtree(str(folder))
            remove_add_subdirectory_line(
                Path(samples_dir, "CMakeLists.txt"), folder
            )
        else:
            print("Keeping directory: " + folder.name + "")

    # Build the sample
    build_dir = test_set_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    cuda_path = os.getenv("CUDA_PATH", "/usr/local/cuda")
    subprocess.run(
        [
            "cmake",
            "-DCMAKE_CUDA_ARCHITECTURES=native",
            "-DCMAKE_CUDA_COMPILER=" + cuda_path + "/bin/nvcc",
            "-DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/",
            "-DCMAKE_INCLUDE_PATH=/usr/local/cuda/include",
            str(test_set_dir),
        ],
        check=True,
        cwd=str(build_dir),
    )

    subprocess.run(
        ["make", "-j", str(os.cpu_count() - 1)],
        cwd=str(build_dir),
        check=True,
    )

    # Add missing files
    # Process based on the value of TEST_SET
    if test_set == "2":
        src_dir = os.path.join(
            str(orig_dir),
            str(test_set),
            "Samples",
            "2_Concepts_and_Techniques",
            "EGLStream_CUDA_Interop",
        )
        dst_dir = os.path.join(
            str(orig_dir),
            str(test_set),
            "build",
            "Samples",
            "2_Concepts_and_Techniques",
            "EGLStream_CUDA_Interop",
            "bin",
        )
        copy_and_set_permissions(src_dir, dst_dir, ".yuv")

    if test_set == "8":
        src_dir = os.path.join(
            str(orig_dir),
            str(test_set),
            "Samples",
            "8_Platform_Specific",
            "Tegra",
            "cudaNvSciBufMultiplanar",
        )
        dst_dir = os.path.join(
            str(orig_dir),
            str(test_set),
            "build",
            "Samples",
            "8_Platform_Specific",
            "Tegra",
            "cudaNvSciBufMultiplanar",
            "bin",
        )
        copy_and_set_permissions(src_dir, dst_dir, ".yuv")

    if test_set == "7":
        src_dir = os.path.join(
            str(orig_dir), str(test_set), "Samples", "7_libNVVM", "ptxgen"
        )
        dst_dir = os.path.join(
            str(orig_dir),
            str(test_set),
            "build",
            "Samples",
            "7_libNVVM",
            "ptxgen",
            "bin",
        )
        copy_and_set_permissions(src_dir, dst_dir, ".ll")


# Function to handle CUDA test exclusions
def get_exclusion_list(
    cuda_ignore_tensorcore, cuda_multigpu, cuda_ignore_tests
):
    exclude_list = []
    if cuda_ignore_tensorcore:
        exclude_list.extend(
            ["dmmaTensorCoreGemm", "tf32TensorCoreGemm", "bf16TensorCoreGemm"]
        )
    if cuda_multigpu != "1":
        exclude_list.extend(
            [
                "simpleP2P",
                "simpleAttributesMPU",
                "simpleCUFFT_MGPU",
                "streamOrderedAllocationP2P",
                "simpleCUFFT_2d_MGPU",
                "conjugateGradientMultiDeviceCG",
            ]
        )
    if cuda_ignore_tests:
        exclude_list.extend(cuda_ignore_tests.split(" "))
    return exclude_list


# Function to run tests
def run_tests(orig_dir, test_set, exclude_list):
    test_set_dir = Path(orig_dir) / test_set / "build" / "Samples"
    file_list = list(test_set_dir.rglob("*/*/bin/*"))
    skipped = 0

    executable_list = []
    for index, exe in enumerate(file_list, 1):
        if os.access(
            str(exe), os.X_OK
        ):  # os.X_OK checks for execute permission
            executable_list.append(exe)

    total = len(executable_list)

    for index, exe in enumerate(executable_list, 1):
        print_colored(
            "green",
            "Step " + str(index) + " of " + str(total) + ": " + str(exe),
        )

        exe_name = exe.name
        excluded = any(exe_name == pattern for pattern in exclude_list)

        if excluded:
            print_colored("red", "Skipping " + str(exe))
            skipped += 1
            continue

        print("Running: " + exe.name + " in " + os.path.dirname(str(exe)))
        exe_args = "test.ll" if exe_name == "ptxgen" else None

        proc = subprocess.run(
            [str(exe), exe_args] if exe_args else [str(exe)],
            check=True,
            cwd=os.path.dirname(str(exe)),
        )

        code = proc.returncode if not isinstance(proc, bool) else 0

        print("Error code : " + str(code))
        # if code != 0:
        #     sys.exit(1)

    print_colored(
        "green",
        "All " + str(total) + " tests done, " + str(skipped) + " skipped.",
    )
    return total, skipped


# Main function to orchestrate the script
def main():
    # Set up the argument parser
    try:
        args = parse_args()
        orig_dir = Path.cwd()
        exclude_list = get_exclusion_list(
            args.cuda_ignore_tensorcore,
            args.cuda_multigpu,
            args.cuda_ignore_tests,
        )

        result = 0
        # Clone and build the repo
        if args.clone != "0":
            clone_and_build(
                orig_dir, str(args.test_set), args.cuda_samples_version
            )

        run_tests(orig_dir, str(args.test_set), exclude_list)
    except Exception:
        print("Test failed", file=sys.stderr)
        result = 1

    if not args.keep_cache == "1":
        exit_trap(orig_dir, str(args.test_set))

    exit(result)


if __name__ == "__main__":
    main()
