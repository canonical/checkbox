#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
#
# Authors:
#   Gabriel Chen <gabriel.chen@canonical.com>
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
"""mouse_key_random utility."""


import evdev
from evdev import UInput, ecodes as e
import time
import random

# Define keyboard keys and mouse buttons
KEYBOARD_KEYS = [
    e.KEY_A,
    e.KEY_B,
    e.KEY_C,
    e.KEY_D,
    e.KEY_E,
    e.KEY_F,
    e.KEY_G,
    e.KEY_H,
    e.KEY_I,
    e.KEY_J,
    e.KEY_K,
    e.KEY_L,
    e.KEY_M,
    e.KEY_N,
    e.KEY_O,
    e.KEY_P,
    e.KEY_Q,
    e.KEY_R,
    e.KEY_S,
    e.KEY_T,
    e.KEY_U,
    e.KEY_V,
    e.KEY_W,
    e.KEY_X,
    e.KEY_Y,
    e.KEY_Z,
    e.KEY_1,
    e.KEY_2,
    e.KEY_3,
    e.KEY_4,
    e.KEY_5,
    e.KEY_6,
    e.KEY_7,
    e.KEY_8,
    e.KEY_9,
    e.KEY_0,
]
MOUSE_BUTTONS = [e.BTN_LEFT, e.BTN_RIGHT]


# Initialize the virtual input device
def dev_init(name):
    # Define the capabilities of the device (keyboard and mouse events)
    capabilities = {
        e.EV_KEY: KEYBOARD_KEYS + MOUSE_BUTTONS,
        e.EV_REL: [e.REL_X, e.REL_Y],
    }
    # Create the virtual input device
    device = UInput(
        capabilities, name=name, vendor=0xBAD, product=0xA55, version=777
    )
    time.sleep(1)  # Give userspace time to detect the new device
    return device


# Destroy the virtual input device
def dev_deinit(device):
    time.sleep(1)  # Give userspace time to read the remaining events
    device.close()


# Simulate a key press
def key_press(device, key):
    device.write(e.EV_KEY, key, 1)  # Press the key
    device.syn()  # Synchronize the event
    device.write(e.EV_KEY, key, 0)  # Release the key
    device.syn()  # Synchronize the event


# Simulate mouse movement
def mouse_move(device, x, y):
    device.write(e.EV_REL, e.REL_X, x)  # Move mouse on the X axis
    device.write(e.EV_REL, e.REL_Y, y)  # Move mouse on the Y axis
    device.syn()  # Synchronize the event


# Randomly press a key
def rand_key_press(device):
    key = random.choice(KEYBOARD_KEYS)  # Choose a random key
    key_press(device, key)  # Simulate the key press
    time.sleep(FREQUENCY_USEC / 1000000.0)  # Wait for the defined frequency


# Randomly move the mouse
def rand_mouse_moves(device):
    # Generate random X and Y movements
    x = random.randint(-MOVE_MAX // 2, MOVE_MAX // 2)
    y = random.randint(-MOVE_MAX // 2, MOVE_MAX // 2)
    steps = max(abs(x), abs(y)) // MOVE_DELTA  # Calculate the number of steps

    # Move the mouse in small steps for smooth movement
    for _ in range(steps):
        mouse_move(device, x // steps, y // steps)
        time.sleep(FREQUENCY_USEC / 1000000.0 / MOVE_DELTA)

    # Handle any remaining movement
    rest_x = x % steps
    rest_y = y % steps
    if rest_x or rest_y:
        mouse_move(device, rest_x, rest_y)
        time.sleep(FREQUENCY_USEC / 1000000.0 / MOVE_DELTA)


# Constants
FREQUENCY_USEC = 100000  # Frequency of events in microseconds
N_EPISODES = 81  # Number of events to generate
WEIGHT_MOUSEMOVE = 10  # Weight of mouse movements
WEIGHT_KEYPRESS = 1  # Weight of key presses
WEIGHT_SUM = WEIGHT_MOUSEMOVE + WEIGHT_KEYPRESS  # Total weight

MOVE_MAX = 100  # Maximum mouse movement distance
MOVE_DELTA = 5  # Mouse movement step size


def main():
    # Initialize the virtual input device
    device = dev_init("umad")
    random.seed(time.time())  # Seed the random number generator

    # Generate random events
    for _ in range(N_EPISODES):
        action = random.randint(0, WEIGHT_SUM - 1)  # Choose a random action
        if action < WEIGHT_MOUSEMOVE:
            rand_mouse_moves(device)  # Simulate mouse movement
        else:
            rand_key_press(device)  # Simulate key press

    # Destroy the virtual input device
    dev_deinit(device)


if __name__ == "__main__":
    main()
