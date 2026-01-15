#!/usr/bin/env python3
import argparse
import evdev
import logging
from evdev import ecodes
from checkbox_support.helpers.timeout import run_with_timeout

# Standard US Keyboard Map (Scancode -> Character)
# This maps the internal Linux event codes to actual characters
KEY_MAP = {
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    16: "q",
    17: "w",
    18: "e",
    19: "r",
    20: "t",
    21: "y",
    22: "u",
    23: "i",
    24: "o",
    25: "p",
    30: "a",
    31: "s",
    32: "d",
    33: "f",
    34: "g",
    35: "h",
    36: "j",
    37: "k",
    38: "l",
    44: "z",
    45: "x",
    46: "c",
    47: "v",
    48: "b",
    49: "n",
    50: "m",
    57: " ",
    28: "\n",
    12: "-",
    52: ".",
}

# Shift Map (For when Shift is held down)
SHIFT_MAP = {
    2: "!",
    3: "@",
    4: "#",
    5: "$",
    6: "%",
    7: "^",
    8: "&",
    9: "*",
    10: "(",
    11: ")",
    12: "_",
    52: ">",
}


def find_device_by_name(name_substring: str):
    """Loops through all input devices to find the one matching the name."""
    logging.info(
        "Searching for device with name: '{}'...".format(name_substring)
    )
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    for device in devices:
        if name_substring in device.name:
            logging.info(
                "Found device: {} at {}".format(device.name, device.path)
            )
            return device

    logging.error("Device not found. Is it plugged in?")
    return None


def listen_and_decode(device: evdev.InputDevice):
    """Listens for events with a timeout and decodes keystrokes."""

    # Grab device to prevent it from typing into other windows
    try:
        device.grab()
    except IOError:
        logging.error("Could not grab device (another app might have it).")

    barcode_buffer = ""
    shift_pressed = False

    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                data = evdev.categorize(event)

                # 42 is Left Shift, 54 is Right Shift
                if data.scancode in [42, 54]:
                    if data.keystate == 1:  # Key Down
                        shift_pressed = True
                    elif data.keystate == 0:  # Key Up
                        shift_pressed = False
                    continue

                # Only process Key Down (1) events
                if data.keystate == 1 and data.scancode in KEY_MAP:
                    char = KEY_MAP[data.scancode]

                    # Handle Capitalization
                    if shift_pressed:
                        # Check specific symbol map first,
                        # then default to .upper()
                        if data.scancode in SHIFT_MAP:
                            char = SHIFT_MAP[data.scancode]
                        else:
                            char = char.upper()

                    if char == "\n":
                        logging.info(
                            "[SUCCESS] Barcode Detected: {}".format(
                                barcode_buffer
                            )
                        )
                        break
                    else:
                        barcode_buffer += char
    finally:
        try:
            device.ungrab()
        except Exception:
            pass


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Barcode Scanner Test")
    parser.add_argument(
        "-n",
        "--name",
        required=True,
        type=str,
        help="Name substring of the target input device",
    )
    parser.add_argument(
        "--check-device",
        action="store_true",
        help="Only check if the device is present",
    )
    args = parser.parse_args()

    # 1. Find the device
    target_device = find_device_by_name(args.name)

    if not target_device:
        raise SystemExit("Target device not found")

    if not args.check_device:
        try:
            run_with_timeout(
                listen_and_decode,
                30,
                target_device,
            )
        except TimeoutError:
            raise SystemExit("Barcode scanning timeout!")
        except KeyboardInterrupt:
            raise SystemExit("Barcode scan stopping manually.")
        finally:
            logging.info("Closing device.")
            target_device.close()


if __name__ == "__main__":
    main()
