#!/usr/bin/env python3
import platform
import argparse
from packaging import version


def main():
    parser = argparse.ArgumentParser(
        description="Check if the current kernel version is at least "
        "the required version."
    )
    parser.add_argument(
        "required_version", help="The minimum required kernel version."
    )
    args = parser.parse_args()

    current_version_str = platform.release()

    current_version = version.Version(current_version_str.rsplit("-", 1)[0])
    required_version = version.Version(args.required_version.rsplit("-", 1)[0])

    if (
        current_version is not None
        and required_version is not None
        and current_version >= required_version
    ):
        print("state: supported")
    else:
        print("state: unsupported")


if __name__ == "__main__":
    main()
