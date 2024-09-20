#!/usr/bin/env python3
import shutil
import argparse
import subprocess

from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--clean", action="store_true")

    return parser.parse_args()


def prepare_repo(repo_root, package_path):
    shutil.move(str(package_path / "debian"), str(repo_root))


def install_build_depends(repo_root):
    subprocess.check_call(
        ["sudo", "apt-get", "-y", "build-dep", "."], cwd=repo_root
    )


def build_package(repo_root):
    # -Pnocheck: skip tests as we have a pipeline that builds/tests debian
    #            packages and doing them on slow machines is a big waste of
    #            time/resources
    subprocess.check_call(["dpkg-buildpackage", "-Pnocheck"], cwd=repo_root)


def install_local_package(repo_root, deb_name_glob):
    # we build in path.parent, dpkg will put the result on ..
    package_list = list(repo_root.parent.glob(deb_name_glob))
    print(f"==== Installing {package_list} ====")
    package_list = [str(x.resolve()) for x in package_list]
    subprocess.check_call(
        [
            "sudo",
            "apt-get",
            "--fix-broken",
            "-y",
            "install",
        ]
        + package_list,
        cwd=repo_root.parent,
        env={"DEBIAN_FRONTEND": "noninteractive"},
    )


def install_package(repo_root, package_path):
    deb_name_glob = f"*{package_path.name}*.deb"
    install_local_package(repo_root, deb_name_glob)


def clean_repo(repo_root):
    subprocess.check_call(["git", "clean", "-xfd", "."], cwd=repo_root)


def build_install_deb(path, clean):
    package_path = path.resolve()

    repo_root = package_path.parent
    if "providers" in str(package_path):
        repo_root = repo_root.parent

    prepare_repo(repo_root, package_path)
    install_build_depends(repo_root)
    build_package(repo_root)
    install_package(repo_root, package_path)
    if clean:
        clean_repo(repo_root)


def main():
    args = parse_args()
    for path in args.paths:
        build_install_deb(path, args.clean)


if __name__ == "__main__":
    main()
