#!/usr/bin/env python3 

import unittest
from unittest.mock import patch, MagicMock
import evdev
from evdev import ecodes as e
import time
import random
from mouse_key_random import (
    dev_init,
    dev_deinit,
    key_press,
    mouse_move,
    rand_key_press,
    rand_mouse_moves,
    main,
    KEYBOARD_KEYS,
    MOUSE_BUTTONS,
    FREQUENCY_USEC,
    MOVE_MAX,
    MOVE_DELTA,
    WEIGHT_MOUSEMOVE,
    WEIGHT_KEYPRESS,
    WEIGHT_SUM,
    N_EPISODES,
)


class TestMouseKeyRandom(unittest.TestCase):

    @patch("evdev.UInput")
    def test_dev_init(self, mock_uinput):
        # Mock the UInput device
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        device = dev_init("test_device")

        # Verify UInput was called with the correct capabilities
        expected_capabilities = {
            e.EV_KEY: KEYBOARD_KEYS + MOUSE_BUTTONS,
            e.EV_REL: [e.REL_X, e.REL_Y],
        }
        mock_uinput.assert_called_once_with(
            expected_capabilities,
            name="test_device",
            vendor=0xBAD,
            product=0xA55,
            version=777,
        )
        self.assertEqual(device, mock_device)

    @patch("evdev.UInput")
    def test_dev_deinit(self, mock_uinput):
        # Mock the UInput device
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        dev_deinit(mock_device)

        # Verify the device was closed
        mock_device.close.assert_called_once()

    @patch("evdev.UInput")
    def test_key_press(self, mock_uinput):
        # Mock the UInput device
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        key_press(mock_device, e.KEY_A)

        # Verify the key press and release events were sent
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 1)  # Key press
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 0)  # Key release
        self.assertEqual(mock_device.syn.call_count, 2)  # Two sync events

    @patch("evdev.UInput")
    def test_mouse_move(self, mock_uinput):
        # Mock the UInput device
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        mouse_move(mock_device, 10, 20)

        # Verify the mouse movement events were sent
        mock_device.write.assert_any_call(e.EV_REL, e.REL_X, 10)  # X movement
        mock_device.write.assert_any_call(e.EV_REL, e.REL_Y, 20)  # Y movement
        mock_device.syn.assert_called_once()  # One sync event

    @patch("mouse_key_random.key_press")
    @patch("mouse_key_random.random.choice")
    def test_rand_key_press(self, mock_random_choice, mock_key_press):
        # Mock the random key selection
        mock_random_choice.return_value = e.KEY_A

        # Mock the UInput device
        mock_device = MagicMock()

        # Call the function
        rand_key_press(mock_device)

        # Verify the key press was simulated
        mock_random_choice.assert_called_once_with(KEYBOARD_KEYS)
        mock_key_press.assert_called_once_with(mock_device, e.KEY_A)

    @patch("mouse_key_random.mouse_move")
    @patch("mouse_key_random.random.randint")
    @patch("mouse_key_random.time.sleep")
    def test_rand_mouse_moves(self, mock_sleep, mock_randint, mock_mouse_move):
        # Mock random mouse movement values
        mock_randint.side_effect = [50, 30]  # X and Y movements

        # Mock the UInput device
        mock_device = MagicMock()

        # Call the function
        rand_mouse_moves(mock_device)

        # Verify the mouse movement was simulated
        expected_steps = max(abs(50), abs(30)) // MOVE_DELTA
        self.assertEqual(mock_mouse_move.call_count, expected_steps + 1)
        mock_sleep.assert_called()

    @patch("mouse_key_random.dev_init")
    @patch("mouse_key_random.dev_deinit")
    @patch("mouse_key_random.rand_mouse_moves")
    @patch("mouse_key_random.rand_key_press")
    @patch("mouse_key_random.random.randint")
    def test_main(
        self,
        mock_randint,
        mock_rand_key_press,
        mock_rand_mouse_moves,
        mock_dev_deinit,
        mock_dev_init,
    ):
        # Mock the random action selection
        mock_randint.side_effect = [0] * N_EPISODES  # Always choose mouse movement

        # Mock the UInput device
        mock_device = MagicMock()
        mock_dev_init.return_value = mock_device

        # Call the main function
        main()

        # Verify the device was initialized and deinitialized
        mock_dev_init.assert_called_once_with("umad")
        mock_dev_deinit.assert_called_once_with(mock_device)

        # Verify the correct number of actions were performed
        self.assertEqual(mock_rand_mouse_moves.call_count, N_EPISODES)
        self.assertEqual(mock_rand_key_press.call_count, 0)


if __name__ == "__main__":
    unittest.main()
