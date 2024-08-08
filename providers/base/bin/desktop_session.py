#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Paolo Gentili <paolo.gentili@canonical.com>

import argparse
import os


def resources():
    """
    Return whether there's a Desktop session and its type.
    """
    is_desktop_session = os.getenv("XDG_CURRENT_DESKTOP") is not None
    print("desktop_session: {}".format(is_desktop_session))
    print("session_type: {}".format(os.getenv("XDG_SESSION_TYPE")))


def main(args=None):
    """
    Retrieve information about the current desktop session.
    """

    if not args:
        parser = argparse.ArgumentParser()
        parser.add_argument("command", choices=["resources"])
        args = parser.parse_args()

    if args.command == "resources":
        return resources()


if __name__ == "__main__":
    main()
