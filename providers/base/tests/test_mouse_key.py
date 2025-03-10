#!/usr/bin/env python3
 
import unittest
from unittest.mock import MagicMock, patch
import time
import random
import evdev
from evdev import UInput, ecodes as e
import mouse_keyboard  # Assuming the original script is named mouse_keyboard.py

class TestMouseKeyboard(unittest.TestCase):

    @patch('mouse_keyboard.UInput')
    def test_dev_init(self, mock_uinput):
        # Mock the UInput object
        mock_device = MagicMock()
        mock_uinput.return_value = mock_device

        # Call the function
        device = mouse_keyboard.dev_init("test_device")

        # Assertions
        mock_uinput.assert_called_once_with(
            {e.EV_KEY: mouse_keyboard.KEYBOARD_KEYS + mouse_keyboard.MOUSE_BUTTONS, e.EV_REL: [e.REL_X, e.REL_Y]},
            name="test_device",
            vendor=0xBAD,
            product=0xA55,
            version=777
        )
        self.assertEqual(device, mock_device)
        time.sleep.assert_called_once_with(1)

    @patch('mouse_keyboard.time.sleep')
    def test_dev_deinit(self, mock_sleep):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        mouse_keyboard.dev_deinit(mock_device)

        # Assertions
        mock_sleep.assert_called_once_with(1)
        mock_device.close.assert_called_once()

    def test_key_press(self):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        mouse_keyboard.key_press(mock_device, e.KEY_A)

        # Assertions
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 1)
        mock_device.write.assert_any_call(e.EV_KEY, e.KEY_A, 0)
        self.assertEqual(mock_device.syn.call_count, 2)

    def test_mouse_move(self):
        # Mock the device
        mock_device = MagicMock()

        # Call the function
        mouse_keyboard.mouse_move(mock_device, 10, 20)

        # Assertions
        mock_device.write.assert_any_call(e.EV_REL, e.REL_X, 10)
        mock_device.write.assert_any_call(e.EV_REL, e.REL_Y, 20)
        mock_device.syn.assert_called_once()

    @patch('mouse_keyboard.random.choice')
    @patch('mouse_keyboard.time.sleep')
    @patch('mouse_keyboard.key_press')
    def test_rand_key_press(self, mock_key_press, mock_sleep, mock_choice):
        # Mock the device
        mock_device = MagicMock()
        mock_choice.return_value = e.KEY_A

        # Call the function
        mouse_keyboard.rand_key_press(mock_device)

        # Assertions
        mock_choice.assert_called_once_with(mouse_keyboard.KEYBOARD_KEYS)
        mock_key_press.assert_called_once_with(mock_device, e.KEY_A)
        mock_sleep.assert_called_once_with(mouse_keyboard.FREQUENCY_USEC / 1000000.0)

    @patch('mouse_keyboard.random.randint')
    @patch('mouse_keyboard.time.sleep')
    @patch('mouse_keyboard.mouse_move')
    def test_rand_mouse_moves(self, mock_mouse_move, mock_sleep, mock_randint):
        # Mock the device
        mock_device = MagicMock()
        mock_randint.side_effect = [50, 30]  # Simulate random x and y values

        # Call the function
        mouse_keyboard.rand_mouse_moves(mock_device)

        # Assertions
        self.assertEqual(mock_randint.call_count, 2)
        self.assertTrue(mock_mouse_move.call_count > 0)
        self.assertTrue(mock_sleep.call_count > 0)

    @patch('mouse_keyboard.random.seed')
    @patch('mouse_keyboard.random.randint')
    @patch('mouse_keyboard.rand_mouse_moves')
    @patch('mouse_keyboard.rand_key_press')
    @patch('mouse_keyboard.dev_init')
    @patch('mouse_keyboard.dev_deinit')
    def test_main(self, mock_dev_deinit, mock_dev_init, mock_rand_key_press, mock_rand_mouse_moves, mock_randint, mock_seed):
        # Mock the device
        mock_device = MagicMock()
        mock_dev_init.return_value = mock_device
        mock_randint.return_value = 5  # Simulate random action selection

        # Call the main function
        mouse_keyboard.main()

        # Assertions
        mock_seed.assert_called_once_with(time.time())
        mock_dev_init.assert_called_once_with("umad")
        self.assertEqual(mock_randint.call_count, mouse_keyboard.N_EPISODES)
        self.assertTrue(mock_rand_mouse_moves.call_count + mock_rand_key_press.call_count, mouse_keyboard.N_EPISODES)
        mock_dev_deinit.assert_called_once_with(mock_device)

if __name__ == "__main__":
    unittest.main()
