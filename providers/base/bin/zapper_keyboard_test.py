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
from enum import Enum

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402

ZAPPER_KBD = "usb-Canonical_Zapper_main_board_123456-event-kbd"
EVENT_BIN_FORMAT = "llHHI"

ROBOT_TESTCASE_COMBO = """
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Press and Release a combination of keys.
    ${keys}=    Create List     A   B
    Keys Combo    ${keys}
"""

ROBOT_TESTCASE_TYPE = """
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Type the requested string
    Type String    hello
"""


class KeyEvent(Enum):
    UP = 0
    DOWN = 1


def _listen_keyboard_events(event_file_path, callback):
    """Listen for keyboard events on the given file."""
    while True:
        read_keyboard_events(event_file_path, callback)


def read_keyboard_events(event_file_path, callback):
    """Read keyboard events from the given file and run the callback."""
    with open(event_file_path, "rb") as event:
        data = event.read(struct.calcsize(EVENT_BIN_FORMAT))
        _, _, event_type, code, value = struct.unpack(EVENT_BIN_FORMAT, data)
        if event_type == 1:  # 0x01 is for _kbd_ events
            callback((KeyEvent(value), code))


def assert_key_combo(host, events):
    """Request to press a key combination and expect the corresponding events."""

    events.clear()
    zapper_run(host, "robot_run", ROBOT_TESTCASE_COMBO.encode(), {}, {})

    assert events == [
        (KeyEvent.DOWN, 30),
        (KeyEvent.DOWN, 48),
        (KeyEvent.UP, 48),
        (KeyEvent.UP, 30),
    ]


def assert_type_string(host, events):
    """Request to type a string and expect the corresponding events."""

    events.clear()
    zapper_run(host, "robot_run", ROBOT_TESTCASE_TYPE.encode(), {}, {})

    assert events == [
        (KeyEvent.DOWN, 35),
        (KeyEvent.UP, 35),
        (KeyEvent.DOWN, 18),
        (KeyEvent.UP, 18),
        (KeyEvent.DOWN, 38),
        (KeyEvent.UP, 38),
        (KeyEvent.DOWN, 38),
        (KeyEvent.UP, 38),
        (KeyEvent.DOWN, 24),
        (KeyEvent.UP, 24),
    ]


def main(argv):
    if len(argv) != 2:
        raise SystemExit("Usage: {} <zapper-ip>".format(argv[0]))

    try:
        event_file = os.path.realpath(f"/dev/input/by-id/{ZAPPER_KBD}", strict=True)
    except FileNotFoundError as exc:
        raise SystemExit("Cannot find Zapper Keyboard.") from exc

    events = []
    threading.Thread(
        target=_listen_keyboard_events, args=(event_file, events.append), daemon=True
    ).start()

    try:
        assert_key_combo(argv[1], events)
        assert_type_string(argv[1], events)
    except AssertionError as exc:
        raise SystemExit("Mismatch in received keyboard events.") from exc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
