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

    list_parser = subparsers.add_parser(
        "list",
        help="List prebuilt samples as Checkbox resource records",
    )
    list_parser.set_defaults(action="list")

    run_parser = subparsers.add_parser(
        "run",
        help="Run one prebuilt sample by name",
    )
    run_parser.add_argument(
        "name", help="Sample name as <category>/<binary>"
    )
    run_parser.set_defaults(action="run")

    parser.add_argument(
        "--samples-path",
        default=os.getenv("CUDA_SAMPLES_PATH", ""),
        help="Path to a pre-built cuda-samples tree (provision-time build).",
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

    if args.cuda_ignore_tensorcore == "1":
        args.cuda_ignore_tests.extend(
            ["dmmaTensorCoreGemm", "tf32TensorCoreGemm", "bf16TensorCoreGemm"]
        )

    if args.cuda_multigpu == "1":
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

    makefile_build = (test_set_dir / "Makefile").exists()

    # Remove unnecessary folders
    samples_dir = test_set_dir / "Samples"
    for folder in samples_dir.glob("[0-9]_*/"):
        folder_number = folder.name.split("_")[0]
        if folder_number != test_set:
            shutil.rmtree(str(folder))
            if not makefile_build:
                remove_add_subdirectory_line(
                    Path(samples_dir, "CMakeLists.txt"), folder
                )
        else:
            logging.info("Keeping directory: %s", folder.name)

    if makefile_build:
        # Makefile-era samples (v12.5 and older): the recursive root
        # Makefile builds each remaining sample and releases its binary
        # into bin/<arch>/linux/release. -k keeps going past samples
        # whose build deps are missing; those are simply not released.
        subprocess.run(
            ["make", "-k", "-j", str(os.cpu_count() - 1)],
            cwd=str(test_set_dir),
            check=False,
        )
        return

    cmake_file = test_set_dir / "CMakeLists.txt"
    cmake_file.write_text(
        "{}\n{}".format(
            'set(EXECUTABLE_OUTPUT_PATH "bin")', cmake_file.read_text()
        )
    )

    # Build the sample
    build_dir = test_set_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    cuda_path = os.getenv("CUDA_PATH", "/usr/local/cuda")
    # native needs a working driver to detect the GPU; allow an explicit
    # override (e.g. 87 for Orin) via CUDA_SAMPLES_ARCHS.
    cuda_archs = os.getenv("CUDA_SAMPLES_ARCHS", "native")
    subprocess.run(
        [
            "cmake",
            "-DCMAKE_CUDA_ARCHITECTURES=" + cuda_archs,
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
        (int, int, [str]): total tests, skipped tests, failed test names
    """
    build_samples = Path(orig_dir) / test_set / "build" / "Samples"
    if build_samples.is_dir():
        executable_list = [
            exe
            for exe in build_samples.rglob("*/*/bin/*")
            if os.access(str(exe), os.X_OK)
        ]
    else:
        # Makefile-era layout: binaries released into bin/<arch>/linux/release
        executable_list = [
            exe
            for release_dir in sorted(
                (Path(orig_dir) / test_set).glob("bin/*/linux/release")
            )
            for exe in sorted(release_dir.iterdir())
            if exe.is_file() and os.access(str(exe), os.X_OK)
        ]

    skipped = 0
    failed = []
    total = len(executable_list)

    for index, exe in enumerate(executable_list, 0):
        logging.info("Step %i of %i: %s", index, total, exe)

        exe_name = exe.name

        if exe_name in exclude_list:
            logging.info("Skipping %s", exe)
            skipped += 1
            continue

        logging.info("Running: %s in %s", exe.name, os.path.dirname(str(exe)))
        exe_args = "test.ll" if exe_name == "ptxgen" else None

        try:
            subprocess.run(
                [str(exe), exe_args] if exe_args else [str(exe)],
                check=True,
                cwd=os.path.dirname(str(exe)),
            )
        except subprocess.CalledProcessError as err:
            logging.error("FAILED (exit %s): %s", err.returncode, exe_name)
            failed.append(exe_name)

    logging.info(
        "All %i tests done; %i skipped, %i failed.",
        total,
        skipped,
        len(failed),
    )
    return total, skipped, failed


# Samples that do not run from a prebuilt Tegra/L4T tree, curated over
# BSP releases by the runner previously shipped to the devices.
PREBUILT_EXCLUDED = [
    "streamOrderedAllocationP2P",
    "conjugateGradientMultiDeviceCG",
    "cuDLAErrorReporting",
    "cuDLAHybridMode",
    "cuDLALayerwiseStatsHybrid",
    "EGLStream_CUDA_CrossGPU",
    "EGLStream_CUDA_Interop",
    "EGLSync_CUDAEvent_Interop",
    "fluidsGLES",
    "nbody_opengles",
    "simpleCUFFT_2d_MGPU",
    "simpleCUFFT_MGPU",
    "simpleGLES",
    "simpleGLES_EGLOutput",
    # test apps we had to exclude since 12.6
    "matrixMul_nvrtc",
    "segmentationTreeThrust",
    "memMapIPCDrv",
    # test apps we had to exclude since 13.0
    "cudaCompressibleMemory",
    "dsl",
    "ptxgen",
    "simple",
    "uvmlite",
    # tests excluded since 13.2 will be reintegrated in future BSP updates
    "nvJPEG",
    "nvJPEG_encoder",
]


def prebuilt_release_dir(samples_path):
    """Return the flat release directory of a provision-time build.

    The provision script releases every built sample (binary or symlink)
    into bin/<arch>/linux/release under the tree root.
    """
    for release_dir in sorted(Path(samples_path).glob("bin/*/linux/release")):
        return release_dir
    return None


def prebuilt_samples(samples_path):
    """Yield (name, path) for the runnable prebuilt samples.

    A sample is runnable on this device when its binary exists in its
    Samples/<category>/<test>/ source directory and was also released
    into the flat bin/<arch>/linux/release directory, i.e. it actually
    built here. name is <category>/<binary>, keeping the upstream sample
    category in the Checkbox job id.
    """
    release_dir = prebuilt_release_dir(samples_path)
    if release_dir is None:
        return
    released = {
        exe.name
        for exe in release_dir.iterdir()
        if os.access(str(exe), os.X_OK)
    }
    samples_dir = Path(samples_path) / "Samples"
    if not samples_dir.is_dir():
        return
    for category in sorted(samples_dir.iterdir()):
        if not category.is_dir():
            continue
        for test in sorted(category.iterdir()):
            if not test.is_dir():
                continue
            for exe in sorted(test.iterdir()):
                if (
                    exe.is_file()
                    and os.access(str(exe), os.X_OK)
                    and exe.name in released
                ):
                    yield "{}/{}".format(category.name, exe.name), exe


def list_prebuilt_samples(args):
    """Print one Checkbox resource record per runnable prebuilt sample.

    Prints nothing (and succeeds) when no prebuilt tree is configured, so
    that plans bootstrapping this resource stay quiet on machines that
    build the samples at test time instead.
    """
    if not args.samples_path or not Path(args.samples_path).is_dir():
        return
    for name, exe in prebuilt_samples(args.samples_path):
        if exe.name in PREBUILT_EXCLUDED or exe.name in args.cuda_ignore_tests:
            continue
        print("name: {}".format(name))
        print("path: {}".format(exe))
        print()


def run_prebuilt_sample(args):
    """Run a single prebuilt sample named <category>/<binary>.

    Samples run from the flat release directory, matching how the tree
    was exercised on the devices so far.
    """
    if not args.samples_path:
        raise SystemExit("CUDA_SAMPLES_PATH is not set")
    for name, exe in prebuilt_samples(args.samples_path):
        if name == args.name:
            release_dir = prebuilt_release_dir(args.samples_path)
            subprocess.run([str(exe)], check=True, cwd=str(release_dir))
            return
    raise SystemExit(
        "Sample {} not found in {}".format(args.name, args.samples_path)
    )


def main():
    args = parse_args()
    logging.basicConfig(level=args.log_level)

    action = getattr(args, "action", "set")
    if action == "list":
        return list_prebuilt_samples(args)
    if action == "run":
        return run_prebuilt_sample(args)

    orig_dir = Path.cwd()

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
        total, _, failed = run_tests(
            orig_dir, str(args.test_set), args.cuda_ignore_tests
        )
    finally:
        if not args.keep_cache:
            cleanup_temporary_files(orig_dir, str(args.test_set))

    if total == 0:
        raise SystemExit("No sample binaries were built for this set")
    if failed:
        raise SystemExit("Failed samples: " + " ".join(failed))


if __name__ == "__main__":
    main()
