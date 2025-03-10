#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock

class TestTouchscreenID(unittest.TestCase):

    @patch('subprocess.run')
    def test_get_touchscreen_id_found(self, mock_run):
        # Mock the output of `xinput list`
        mock_output = """
⎡ Virtual core pointer                    	id=2	[master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer              	id=4	[slave  pointer  (2)]
⎜   ↳ ELAN Touchscreen                        	id=10	[slave  pointer  (2)]
⎣ Virtual core keyboard                   	id=3	[master keyboard (2)]
    ↳ Virtual core XTEST keyboard             	id=5	[slave  keyboard (3)]
    ↳ Power Button                            	id=6	[slave  keyboard (3)]
    ↳ Video Bus                               	id=7	[slave  keyboard (3)]
    ↳ Power Button                            	id=8	[slave  keyboard (3)]
    ↳ Sleep Button                            	id=9	[slave  keyboard (3)]
"""
        mock_run.return_value = MagicMock(stdout=mock_output, stderr='', returncode=0)
        
        # Call the function and verify the result
        touchscreen_id = get_touchscreen_id()
        self.assertEqual(touchscreen_id, 10)

    @patch('subprocess.run')
    def test_get_touchscreen_id_not_found(self, mock_run):
        # Mock the output of `xinput list` with no touchscreen
        mock_output = """
⎡ Virtual core pointer                    	id=2	[master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer              	id=4	[slave  pointer  (2)]
⎣ Virtual core keyboard                   	id=3	[master keyboard (2)]
    ↳ Virtual core XTEST keyboard             	id=5	[slave  keyboard (3)]
    ↳ Power Button                            	id=6	[slave  keyboard (3)]
    ↳ Video Bus                               	id=7	[slave  keyboard (3)]
    ↳ Power Button                            	id=8	[slave  keyboard (3)]
    ↳ Sleep Button                            	id=9	[slave  keyboard (3)]
"""
        mock_run.return_value = MagicMock(stdout=mock_output, stderr='', returncode=0)
        
        # Call the function and verify the result
        touchscreen_id = get_touchscreen_id()
        self.assertIsNone(touchscreen_id)

    @patch('subprocess.run')
    def test_get_touchscreen_id_error(self, mock_run):
        # Simulate a command execution failure
        mock_run.return_value = MagicMock(stdout='', stderr='Error', returncode=1)
        
        # Call the function and verify the result
        touchscreen_id = get_touchscreen_id()
        self.assertIsNone(touchscreen_id)

if __name__ == '__main__':
    unittest.main()
