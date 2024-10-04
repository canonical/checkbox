#!/usr/bin/env python3
"""
This program tests whether the system responds correctly to an external
USB keyboard.

To run the test you need Zapper board connected and set up.
"""
import os
import struct
import sys
import threading
import time
from enum import Enum
from pathlib import Path

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402

ROBOT_INIT = """
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Do nothing
    Log    Re-configure HID device
"""


ROBOT_MOUSE = """
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Click in the middle of the screen
    [Documentation]     Click a button
    Move Mouse To Absolute  500    1000
    Click Pointer Button    LEFT
"""


def main(argv):
    """
    Request Zapper to type on keyboard and assert the received events
    are like expected.
    """

    if len(argv) != 2:
        raise SystemExit("Usage: {} <zapper-ip>".format(argv[0]))


    print("Running the mouse test")
    result = zapper_run(argv[1], "robot_run", ROBOT_INIT.encode(), {}, {})
    result = zapper_run(argv[1], "robot_run", ROBOT_MOUSE.encode(), {}, {})
    print(len(result))
    # save result[1] to an html file
    with open("mouse_test.html", "w") as f:
        f.write(result[1])



if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
