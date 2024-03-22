import unittest
import platform_profile_resource
from unittest.mock import patch

class TestPlatformProfilesSupport(unittest.TestCase):
    # Test the check_platform_profiles function
    @patch("builtins.print")
    def test_supported(self, mock_print):
        with patch('pathlib.Path.exists') as mock_exists:
            # All paths exist
            mock_exists.side_effect = [True, True, True]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_once_with('supported: True')

    @patch("builtins.print")
    def test_unsupported(self, mock_print):
        with patch('pathlib.Path.exists') as mock_exists:
            # First scenario: None of the paths exist
            mock_exists.side_effect = [False, False, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_once_with('supported: False')
            
            # Second scenario: Only sysfs_root exists
            mock_exists.side_effect = [True, False, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with('supported: False')
            self.assertEqual(mock_print.call_count, 2)
            
            # Third scenario: sysfs_root and choices_path exist, but profile_path does not exist
            mock_exists.side_effect = [True, True, False]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with('supported: False')
            self.assertEqual(mock_print.call_count, 3)

            # Fourth scenario: sysfs_root and profile_path exist, but choices_path does not exist
            mock_exists.side_effect = [True, False, True]
            platform_profile_resource.check_platform_profiles()
            # Check the output
            mock_print.assert_called_with('supported: False')
            self.assertEqual(mock_print.call_count, 4)

    @patch("platform_profile_resource.check_platform_profiles")
    def test_main(self, mock_check_platform_profiles):
        # Call the function
        platform_profile_resource.main()
        # Check the output
        mock_check_platform_profiles.assert_called()
