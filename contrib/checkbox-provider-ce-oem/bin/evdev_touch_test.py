#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
# Reference links:
# https://www.kernel.org/doc/html/v4.18/input/multi-touch-protocol.html
# https://docs.kernel.org/input/event-codes.html

import argparse
import time
import threading
import queue
import evdev
from evdev.ecodes import EV_ABS  # touch event on touchscreen
from evdev.ecodes import ABS_MT_SLOT
from evdev.ecodes import ABS_MT_POSITION_X
from evdev.ecodes import ABS_MT_POSITION_Y
from evdev.ecodes import ABS_MT_TRACKING_ID
from evdev.ecodes import EV_KEY
from evdev.ecodes import BTN_TOUCH
from evdev.ecodes import ABS_X
from evdev.ecodes import ABS_Y
from evdev.ecodes import EV_SYN
from evdev.ecodes import SYN_REPORT
from evdev.evtest import print_event


def register_arguments():

    parser = argparse.ArgumentParser()
    parser.add_argument("name", help='Touch device product name')
    parser.add_argument("--timeout", type=int, default=10, help='timeout')
    parser.add_argument(
        "--xfingers", "-x", type=int, default=1, help="X-fingers tap event")

    return parser.parse_args()


def filter_touchscreen_event(events):

    touch_events_state = {
        EV_KEY: {BTN_TOUCH: False},
        EV_ABS: {
            ABS_X: False,
            ABS_Y: False,
            ABS_MT_SLOT: False,
            ABS_MT_TRACKING_ID: False,
            ABS_MT_POSITION_X: False,
            ABS_MT_POSITION_Y: False
        },
        "mt_slots": []
    }
    filter_events = []
    for ev in events:
        if ev.type in touch_events_state.keys() and \
           ev.code in touch_events_state.get(ev.type, {}).keys():
            touch_events_state[ev.type][ev.code] = True
            if ev.code == ABS_MT_SLOT:
                touch_events_state["mt_slots"].append(ev.value)
            filter_events.append(ev)

    return touch_events_state, filter_events


def check_single_touch_event(detect_state):
    """
    Check single touch events are captured.
    When the touchscren is a pointer device
    Expected events are BTN_TOUCH, ABS_X and ABS_Y

    When the touchscreen is a pure mt device
    Expected events are
        ABS_MT_TRACKING_ID
        ABS_MT_POSITION_X
        ABS_MT_POSITION_Y
    """
    result = False
    if len(detect_state["mt_slots"]) == 1 and \
       detect_state["mt_slots"][0] == 0:
        expect_slot = True
    else:
        expect_slot = False

    if detect_state[EV_ABS][ABS_MT_TRACKING_ID] and \
            detect_state[EV_ABS][ABS_MT_POSITION_X] and \
            detect_state[EV_ABS][ABS_MT_POSITION_Y] and \
            (expect_slot or len(detect_state["mt_slots"]) == 0):
        result = True
    elif detect_state[EV_KEY][BTN_TOUCH] and \
            detect_state[EV_ABS][ABS_X] and \
            detect_state[EV_ABS][ABS_Y]:
        result = True
    else:
        print("\n#### Touch events are not expected")

    return result


def check_multiple_touch_event(detect_state, slot_num):
    """
    Check multiple touch events are captured.
    Expected events are
        ABS_MT_SLOT
        ABS_MT_TRACKING_ID
        ABS_MT_POSITION_X
        ABS_MT_POSITION_Y
    For the ABS_MT_SLOT event, the value should be equal to (tap - 1)
    """
    expect_slot = result = False
    for slot in detect_state["mt_slots"]:
        if slot == (slot_num - 1):
            expect_slot = True

    if detect_state[EV_ABS][ABS_MT_SLOT] and \
            detect_state[EV_ABS][ABS_MT_TRACKING_ID] and \
            detect_state[EV_ABS][ABS_MT_POSITION_X] and \
            detect_state[EV_ABS][ABS_MT_POSITION_Y] and \
            expect_slot:
        result = True
    else:
        print("\n#### Touch events are not expected")

    return result


def capture_events(device, event_queue):
    for event in device.read_loop():
        event_queue.put(event)


def main():
    """
    the scripts would capture all touch events to queue by
    evdev module in background, and compare the event
    one by one once received a SYN_REPORT event

    ## For the single touch event
    option 1:
        a BTN_TOUCH, ABS_X and ABS_Y is required in a event group
    option 2:
        ABS_MT_TRACKING_ID, ABS_MT_POSITION_X and ABS_MT_POSITION_Y
        is required in a event group, the ABS_MT_SLOT event must not exist
    option 3:
        ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y
        and ABS_MT_SLOT is required in a event group,
        only one ABS_MT_SLOT is received
        and the value of ABS_MT_SLOT event must be 0

    ## For the multiple touch event
        ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y
        and ABS_MT_SLOT is required in a event group.
        the value of ABS_MT_SLOT event must be (tap number - 1)
    """

    args = register_arguments()
    due_time = time.time() + args.timeout

    print("\n### Available input devices:")
    for d in [evdev.InputDevice(path) for path in evdev.list_devices()]:
        print("- {}".format(d.name))
        if d.name == args.name:
            device = d
            break
    else:
        raise SystemExit("Touch device not found!")
    expected_tap = args.xfingers

    print("\n### Start to capture events from {}".format(d.name))
    events = []
    result = False
    event_queue = queue.SimpleQueue()
    proc = threading.Thread(
            target=capture_events,
            args=(device, event_queue,))
    proc.daemon = True
    proc.start()

    while True:
        if time.time() > due_time:
            d.close()
            raise TimeoutError("Event not detected")

        if event_queue.empty():
            continue

        event = event_queue.get_nowait()
        if event.type == EV_SYN and event.code == SYN_REPORT:
            detect_state, filter_events = filter_touchscreen_event(events)
            if expected_tap == 1:
                result = check_single_touch_event(detect_state)
            else:
                result = check_multiple_touch_event(detect_state, expected_tap)

            # Dump touch events
            for ev in filter_events:
                print_event(ev)

            if result:
                print(
                    ("\n#### {} touch event "
                     "detected seccessfully").format(expected_tap)
                )
                break
            events = []
        else:
            events.append(event)
    print("### Stop to capture events from {}".format(d.name))


if __name__ == "__main__":
    main()
