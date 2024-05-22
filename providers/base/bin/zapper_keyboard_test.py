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
from pathlib import Path

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402


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
    """Key events of interest."""

    UP = 0
    DOWN = 1


class KeyboardListener(threading.Thread):
    """Listen for keyboard events."""

    EVENT_BIN_FORMAT = "llHHI"  # expected data layout
    EVENT_BIN_SIZE = struct.calcsize(EVENT_BIN_FORMAT)

    def __init__(self, event_file, callback):
        super().__init__()
        self._keep_running = True
        self._event_no = os.open(event_file, os.O_NONBLOCK | os.O_RDONLY)
        self._callback = callback

    def run(self):
        """Start polling keyboard events."""
        while self._keep_running:
            self._read_keyboard_events()

    def stop(self):
        """Stop loop and close the file."""
        self._keep_running = False
        os.close(self._event_no)

    def _read_keyboard_events(self):
        """Read keyboard events from the given file and run the callback."""

        try:
            data = os.read(self._event_no, self.EVENT_BIN_SIZE)
        except BlockingIOError:
            return

        _, _, event_type, code, value = struct.unpack(
            self.EVENT_BIN_FORMAT, data
        )
        if event_type == 1:  # 0x01 is for _kbd_ events
            self._callback((KeyEvent(value), code))


def assert_key_combo(host, events):
    """
    Request to press a key combination and expect the corresponding events.
    """

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


def get_zapper_kbd_device():
    """
    Get Zapper keyboard device by ID.

    Being a composite device, interface number might change depending on
    Zapper HID configuration.
    """
    zapper_kbd = "usb-Canonical_Zapper_main_board_123456*-event-kbd"

    for file_path in Path("/dev/input/by-id/").glob(zapper_kbd):
        return str(file_path)
    raise FileNotFoundError("Cannot find Zapper Keyboard.")


def main(argv):
    """
    Request Zapper to type on keyboard and assert the received events
    are like expected.
    """

    if len(argv) != 2:
        raise SystemExit("Usage: {} <zapper-ip>".format(argv[0]))

    try:
        zapper_kbd = get_zapper_kbd_device()
    except FileNotFoundError as exc:
        raise SystemExit("Cannot find Zapper Keyboard.") from exc

    if not os.access(zapper_kbd, os.R_OK):
        raise SystemExit("Cannot read from Zapper Keyboard.")

    events = []
    listener = KeyboardListener(zapper_kbd, events.append)
    listener.start()

    try:
        assert_key_combo(argv[1], events)
        assert_type_string(argv[1], events)
    except AssertionError as exc:
        raise SystemExit("Mismatch in received keyboard events.") from exc
    finally:
        listener.stop()
        listener.join()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
