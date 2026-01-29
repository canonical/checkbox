#!/usr/bin/env python3
import platform
import argparse
import re


def parse_version(version_str):
    try:
        # Find all sequences of one or more digits in the string
        numbers = re.findall(
            r"\d+",
            version_str,
        )
        if not numbers:
            raise ValueError("No version numbers found in the string.")

        # Convert the list of number strings to a tuple of integers
        return tuple(
            map(
                int,
                numbers,
            )
        )
    except (
        ValueError,
        TypeError,
    ):
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Check if the current kernel version is at least the \
        required version."
    )
    parser.add_argument(
        "required_version",
        help="The minimum required kernel version.",
    )
    args = parser.parse_args()

    current_version_str = platform.release()

    current_version = parse_version(current_version_str)
    required_version = parse_version(args.required_version)

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
