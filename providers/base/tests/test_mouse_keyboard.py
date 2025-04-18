#!/usr/bin/env python3
import unittest
from unittest.mock import MagicMock, patch
import time
import random
import evdev
from evdev import ecodes as e
from mouse_keyboard import (
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


class TestMouseKeyboard(unittest.TestCase):

    @patch("mouse_keyboard.UInput")
    @patch("mouse_keyboard.time.sleep")
    def test_dev_init(self, mock_sleep, mock_uinput):
        # Mock the UInput class
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        device = dev_init("umad")

        # Assertions
        mock_uinput.assert_called_once_with(
            {
                e.EV_KEY: KEYBOARD_KEYS + MOUSE_BUTTONS,
                e.EV_REL: [e.REL_X, e.REL_Y],
            },
            name="umad",
            vendor=0xBAD,
            product=0xA55,
            version=777,
        )
        self.assertEqual(device, mock_device)
        mock_sleep.assert_called_once_with(1)

    @patch("mouse_keyboard.time.sleep")
    def test_dev_deinit(self, mock_sleep):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        dev_deinit(mock_device)

        # Assertions
        mock_sleep.assert_called_once_with(1)
        mock_device.close.assert_called_once_with()

    def test_key_press(self):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        key_press(mock_device, e.KEY_A)

        # Assertions
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 1)
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 0)
        self.assertEqual(mock_device.syn.call_count, 2)

    def test_mouse_move(self):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        mouse_move(mock_device, 10, 20)

        # Assertions
        mock_device.write.assert_any_call(e.EV_REL, e.REL_X, 10)
        mock_device.write.assert_any_call(e.EV_REL, e.REL_Y, 20)
        mock_device.syn.assert_called_once_with()

    @patch("mouse_keyboard.random.choice")
    @patch("mouse_keyboard.time.sleep")
    def test_rand_key_press(self, mock_sleep, mock_choice):
        # Mock the device and random choice
        mock_device = MagicMock()
        mock_choice.return_value = e.KEY_B

        # Call the function
        rand_key_press(mock_device)

        # Assertions
        mock_choice.assert_called_once_with(KEYBOARD_KEYS)
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_B, 1)
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_B, 0)
        mock_sleep.assert_called_once_with(FREQUENCY_USEC / 1000000.0)

    @patch("mouse_keyboard.random.randint")
    @patch("mouse_keyboard.time.sleep")
    def test_rand_mouse_moves(self, mock_sleep, mock_randint):
        # Mock the device and random.randint
        mock_device = MagicMock()
        mock_randint.side_effect = [50, -30]  # x, y

        # Call the function
        rand_mouse_moves(mock_device)

        # Assertions
        self.assertEqual(mock_randint.call_count, 2)
        mock_device.write.assert_any_call(
            e.EV_REL, e.REL_X, 50 // (50 // MOVE_DELTA)
        )
        mock_device.write.assert_any_call(
            e.EV_REL, e.REL_Y, -30 // (50 // MOVE_DELTA)
        )
        self.assertGreaterEqual(mock_sleep.call_count, 1)

    @patch("mouse_keyboard.time.time")
    @patch("mouse_keyboard.rand_mouse_moves")
    @patch("mouse_keyboard.random.seed")
    @patch("mouse_keyboard.random.randint")
    @patch("mouse_keyboard.dev_init")
    @patch("mouse_keyboard.dev_deinit")
    def test_main(
        self,
        mock_dev_deinit,
        mock_dev_init,
        mock_randint,
        mock_seed,
        mock_rand_mouse_moves,
        mock_time,
    ):
        # Mock the device and random functions
        mock_device = MagicMock()
        mock_dev_init.return_value = mock_device
        mock_randint.side_effect = [
            0,
            10,
        ] * N_EPISODES  # Always choose mouse movement

        # Call the function
        main()

        # Assertions
        mock_seed.assert_called_once_with(mock_time())
        mock_dev_init.assert_called_once_with("umad")
        self.assertEqual(mock_randint.call_count, N_EPISODES)
        mock_dev_deinit.assert_called_once_with(mock_device)


if __name__ == "__main__":
    unittest.main()
