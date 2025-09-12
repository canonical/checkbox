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
import logging
import os
import shutil
import subprocess

from pathlib import Path


def cleanup_temporary_files(orig_dir, test_set):
    """Cleanup the files and folder that were created during the tests

    Args:
        orig_dir (Path): Path of the root folder
        test_set (number): Index of the test set
    """
    test_set_dir = Path(orig_dir) / test_set
    logging.info("Cleaning up %s", test_set_dir)
    shutil.rmtree(str(test_set_dir), ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a set of CUDA tests with customizable configurations."
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        default=logging.INFO,
        const=logging.DEBUG,
        help="Increase logging level",
    )

    parser.set_defaults(missing_files=[])

    # sub parsers
    subparsers = parser.add_subparsers(required=True)
    intro_parser = subparsers.add_parser("introduction", help="Introduction")
    intro_parser.set_defaults(test_set=0)

    utilities_parser = subparsers.add_parser("utilities", help="Utilities")
    utilities_parser.set_defaults(test_set=1)

    concepts_parser = subparsers.add_parser(
        "concepts", help="Concepts_and_Techniques"
    )
    concepts_parser.set_defaults(test_set=2)
    concepts_parser.set_defaults(
        missing_files=[
            # list of tuple with src, dest, and extension ?
            (
                Path("Samples")
                / "2_Concepts_and_Techniques"
                / "EGLStream_CUDA_Interop",
                Path("build")
                / "Samples"
                / "2_Concepts_and_Techniques"
                / "EGLStream_CUDA_Interop"
                / "bin",
                ".yuv",
            )
        ]
    )

    features_parser = subparsers.add_parser("features", help="CUDA_Features")
    features_parser.set_defaults(test_set=3)

    libraries_parser = subparsers.add_parser(
        "libraries", help="CUDA_Libraries"
    )
    libraries_parser.set_defaults(test_set=4)

    domain_parser = subparsers.add_parser("domain", help="Domain_Specific")
    domain_parser.set_defaults(test_set=5)

    performance_parser = subparsers.add_parser(
        "performance", help="Performance"
    )
    performance_parser.set_defaults(test_set=6)

    libnvvm_parser = subparsers.add_parser("libnvvm", help="libNVVM")
    libnvvm_parser.set_defaults(test_set=7)
    libnvvm_parser.set_defaults(
        missing_files=[
            (
                Path("Samples") / "7_libNVVM" / "ptxgen",
                Path("build") / "Samples" / "7_libNVVM" / "ptxgen" / "bin",
                ".ll",
            )
        ]
    )

    platform_parser = subparsers.add_parser(
        "platform", help="Platform_Specific"
    )
    platform_parser.set_defaults(test_set=8)
    platform_parser.set_defaults(
        missing_files=[
            (
                Path("Samples")
                / "8_Platform_Specific"
                / "Tegra"
                / "cudaNvSciBufMultiplanar",
                Path("build")
                / "Samples"
                / "8_Platform_Specific"
                / "Tegra"
                / "cudaNvSciBufMultiplanar"
                / "bin",
                ".yuv",
            )
        ]
    )

    parser.add_argument(
        "--cuda-samples-version",
        default=os.getenv("CUDA_SAMPLES_VERSION", "12.8"),
        help="CUDA samples version.",
    )
    parser.add_argument(
        "--cuda-ignore-tensorcore",
        default=os.getenv("CUDA_IGNORE_TENSORCORE", "0"),
        choices=["0", "1"],
        help="Ignore TensorCores if the machine does not have them.",
    )
    parser.add_argument(
        "--cuda-multigpu",
        default=os.getenv("CUDA_MULTIGPU", "0"),
        choices=["0", "1"],
        help="Enable if the machine has multiple NVIDIA GPUs.",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="[DEBUG] Don't clone the repo",
    )
    parser.add_argument(
        "--keep-cache",
        action="store_true",
        help="[DEBUG] Keep the cache",
    )

    parser.add_argument(
        "--cuda-ignore-tests",
        default=os.getenv("CUDA_IGNORE_TESTS", ""),
        help="Space-separated list of tests to ignore.",
    )

    args = parser.parse_args()

    args.cuda_ignore_tests = (
        args.cuda_ignore_tests.strip().split(" ")
        if args.cuda_ignore_tests and args.cuda_ignore_tests.strip()
        else []
    )

    if args.cuda_ignore_tensorcore:
        args.cuda_ignore_tests.extend(
            ["dmmaTensorCoreGemm", "tf32TensorCoreGemm", "bf16TensorCoreGemm"]
        )

    if args.cuda_multigpu:
        args.cuda_ignore_tests.extend(
            [
                "simpleP2P",
                "simpleAttributesMPU",
                "simpleCUFFT_MGPU",
                "streamOrderedAllocationP2P",
                "simpleCUFFT_2d_MGPU",
                "conjugateGradientMultiDeviceCG",
            ]
        )

    return args


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
    Path(dst).mkdir(parents=True, exist_ok=True)

    # Copy the files with the given extension
    for filename in os.listdir(str(src)):
        if filename.endswith(file_extension):
            shutil.copy(os.path.join(src, filename), dst)

            # Set file permissions to remove execute bit
            file_path = os.path.join(dst, filename)
            os.chmod(file_path, 0o644)


def clone_and_build(orig_dir, test_set, cuda_samples_version):
    """Function to clone the repository and build the correct subfolder

    Args:
        orig_dir (Path): Path of the root folder
        test_set (number): index of the set (0 to 8)
        cuda_samples_version (_type_): tag to clone (ex: 12.8)

    """
    test_set_dir = Path(orig_dir) / test_set
    if test_set_dir.exists():
        raise FileExistsError("Error: folder {} exists".format(test_set_dir))

    logging.info(
        "Cloning CUDA Samples v%s. Version can be set in the manifest.",
        cuda_samples_version,
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
    cmake_file.write_text(
        "{}\n{}".format(
            'set(EXECUTABLE_OUTPUT_PATH "bin")', cmake_file.read_text()
        )
    )

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
            logging.info("Keeping directory: %s", folder.name)

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


# Function to run tests
def run_tests(orig_dir, test_set, exclude_list):
    """Run the test

    Args:
        orig_dir (Path): path of the root folder
        test_set (_type_): index of the set (0 to 8)
        exclude_list ([str]): list of test to skip

    Returns:
        (int, int): total tests, skipped tests
    """
    test_set_dir = Path(orig_dir) / test_set / "build" / "Samples"

    executable_list = [
        exe
        for exe in test_set_dir.rglob("*/*/bin/*")
        if os.access(str(exe), os.X_OK)
    ]

    skipped = 0
    total = len(executable_list)

    for index, exe in enumerate(executable_list, 0):
        logging.info("Step %i of %i: %s", index, total, exe)

        exe_name = exe.name
        excluded = any(exe_name == pattern for pattern in exclude_list)

        if excluded:
            logging.info("Skipping %s", exe)
            skipped += 1
            continue

        logging.info("Running: %s in %s", exe.name, os.path.dirname(str(exe)))
        exe_args = "test.ll" if exe_name == "ptxgen" else None

        proc = subprocess.run(
            [str(exe), exe_args] if exe_args else [str(exe)],
            check=True,
            cwd=os.path.dirname(str(exe)),
        )

        code = proc.returncode if not isinstance(proc, bool) else 0

        logging.error("Error code : " + str(code))

    logging.info("All %i tests done,; %s skipped.", total, skipped)
    return total, skipped


def main():
    args = parse_args()
    orig_dir = Path.cwd()
    logging.basicConfig(level=args.log_level)

    try:
        if not args.no_clone:
            clone_and_build(
                orig_dir, str(args.test_set), args.cuda_samples_version
            )
    except (subprocess.CalledProcessError, FileExistsError, OSError):
        if not args.keep_cache:
            cleanup_temporary_files(orig_dir, str(args.test_set))
        raise

    for src, dest, extension in args.missing_files:
        copy_and_set_permissions(
            orig_dir / str(args.test_set) / src,
            orig_dir / str(args.test_set) / dest,
            extension,
        )

    try:
        run_tests(orig_dir, str(args.test_set), args.cuda_ignore_tests)

    except subprocess.CalledProcessError:
        logging.error("Test failed")
        if not args.keep_cache:
            cleanup_temporary_files(orig_dir, str(args.test_set))
        raise

    if not args.keep_cache:
        cleanup_temporary_files(orig_dir, str(args.test_set))


if __name__ == "__main__":
    main()
