#!/usr/bin/env python3

import sys
import re

from argparse import ArgumentParser
from subprocess import check_output

TYPES = ("source", "sink")

active_entries_regex = re.compile(r"\* index.*?(?=properties)", re.DOTALL)
entries_regex = re.compile(r"index.*?(?=properties)", re.DOTALL)
index_regex = re.compile(r"(?<=index: )[0-9]*")
muted_regex = re.compile(r"(?<=muted: ).*")
volume_regex = re.compile(r"(?<=volume: 0: )\s*[0-9]*")
name_regex = re.compile(r"(?<=name:).*")


def check_muted():
    """
    Checks that the active source/sink are not muted.  This does not test
    inactive sources/sinks.
    """
    retval = 0
    for vtype in TYPES:
        try:
            pacmd_entries = check_output(
                ["pacmd", "list-%ss" % vtype], universal_newlines=True
            )
        except Exception as e:
            print(
                "Error when running pacmd list-%ss: %s" % (vtype, e),
                file=sys.stderr,
            )
            return 1

        active_entry_match = active_entries_regex.search(pacmd_entries)
        if active_entry_match:
            active_entry = active_entry_match.group()
        else:
            print(
                "Unable to find a %s active_entry in the pacmd list-%ss"
                " output\npacmd output was: %s"
                % (vtype, vtype, pacmd_entries),
                file=sys.stderr,
            )
            return 1

        name_match = name_regex.search(active_entry)
        if name_match:
            name = name_match.group()
        else:
            print(
                "Unable to determine device bus information from the"
                " pacmd list-%ss output\npacmd output was: %s"
                % (vtype, pacmd_entries),
                file=sys.stderr,
            )
            return 1

        muted_match = muted_regex.search(active_entry)
        if muted_match:
            muted = muted_match.group().strip()
            if muted.lower() == "yes":
                print("FAIL: Audio is muted on %s %s" % (name, vtype))
                retval = 1
            else:
                print("PASS: Audio is not muted on %s %s" % (name, vtype))
        else:
            print(
                "Unable to find mute information in the pacmd list-%ss"
                " output for device %s\npacmd output was: %s"
                % (vtype, name, pacmd_entries),
                file=sys.stderr,
            )
            return 1
    return retval


def check_volume(minvol, maxvol):
    """
    Checks that the volume for all sources/sinks is between min and max.
    Volume must be < min and > max to pass.
    """

    retval = 0
    for vtype in TYPES:
        try:
            pacmd_entries = check_output(
                ["pacmd", "list-%ss" % vtype], universal_newlines=True
            )
        except Exception as e:
            print(
                "Error when running pacmd list-%ss: %s" % (vtype, e),
                file=sys.stderr,
            )
            return 1

        entries = entries_regex.findall(pacmd_entries)

        for entry in entries:
            name_match = name_regex.search(entry)
            if name_match:
                name = name_match.group()
            else:
                print(
                    "Unable to determine device bus information from the"
                    " pacmd list-%ss output\npacmd output was: %s"
                    % (vtype, pacmd_entries),
                    file=sys.stderr,
                )
                return 1

            volume_match = volume_regex.search(entry)
            if volume_match:
                volume = int(volume_match.group().strip())
                if volume > maxvol:
                    print(
                        "FAIL: Volume of %d is greater than"
                        " maximum of %d for %s %s"
                        % (volume, maxvol, name, vtype)
                    )
                    retval = 1
                elif volume < minvol:
                    print(
                        "FAIL: Volume of %d is less than"
                        " minimum of %d for %s %s"
                        % (volume, minvol, name, vtype)
                    )
                    retval = 1
                else:
                    print(
                        "PASS: Volume is %d for %s %s" % (volume, name, vtype)
                    )
            else:
                print(
                    "Unable to find volume information in the pacmd"
                    "  list-%ss output for device %s.\npacmd output "
                    "was: %s" % (vtype, name, pacmd_entries),
                    file=sys.stderr,
                )
                return 1
    return retval


def main():
    parser = ArgumentParser("Check the audio volume")
    parser.add_argument(
        "-n",
        "--minvol",
        type=int,
        required=True,
        help="""The minimum volume for a check_volume call.
                                Volume must be greater than this number to
                                be considered a pass.""",
    )
    parser.add_argument(
        "-x",
        "--maxvol",
        type=int,
        required=True,
        help="""The maximum volume for a check_volume call.
                                Volume must be less than this number to
                                be considered a pass.""",
    )
    args = parser.parse_args()

    check_muted_retval = check_muted()
    check_volume_retval = check_volume(args.minvol, args.maxvol)
    return check_muted_retval or check_volume_retval


if __name__ == "__main__":
    sys.exit(main())
