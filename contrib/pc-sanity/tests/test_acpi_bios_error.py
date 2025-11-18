import unittest
from unittest.mock import patch, mock_open
import subprocess
import sys
import os

# Add the bin directory to sys.path to import the module
# sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bin'))
from acpi_bios_error import get_bios_info, check_acpi_bios_errors, main


class TestAcpiBiosError(unittest.TestCase):

    def test_get_bios_info_success(self):
        """Test successful BIOS info collection."""
        mock_files = {
            '/sys/class/dmi/id/bios_date': '02/29/2024',
            '/sys/class/dmi/id/bios_release': '1.2.3',
            '/sys/class/dmi/id/bios_vendor': 'Test Vendor',
            '/sys/class/dmi/id/bios_version': '2.4.0'
        }
        
        def mock_open_func(path, mode='r'):
            if path in mock_files:
                return mock_open(read_data=mock_files[path])()
            raise FileNotFoundError(f"No such file: {path}")
        
        with patch('builtins.open', side_effect=mock_open_func):
            bios_info = get_bios_info()
            
        self.assertEqual(bios_info['date'], '02/29/2024')
        self.assertEqual(bios_info['release'], '1.2.3')
        self.assertEqual(bios_info['vendor'], 'Test Vendor')
        self.assertEqual(bios_info['version'], '2.4.0')

    @patch('subprocess.check_output')
    def test_check_acpi_bios_errors_no_errors(self, mock_subprocess):
        """Test when no ACPI BIOS errors are found."""
        # Mock journalctl output without ACPI BIOS errors
        mock_subprocess.return_value = """
        Jan 01 12:00:00 hostname kernel: Linux version 6.5.0-generic
        Jan 01 12:00:01 hostname kernel: Command line: root=/dev/sda1
        Jan 01 12:00:02 hostname kernel: ACPI: DSDT table loaded
        """
        
        # Should not raise SystemExit
        check_acpi_bios_errors()
        mock_subprocess.assert_called_once_with(
            ["journalctl", "-b", "-k"],
            universal_newlines=True,
            stderr=subprocess.STDOUT
        )

    @patch('subprocess.check_output')
    def test_check_acpi_bios_errors_found(self, mock_subprocess):
        """Test when ACPI BIOS errors are detected."""
        # Mock journalctl output with ACPI BIOS error
        mock_subprocess.return_value = """
        Jan 01 12:00:00 hostname kernel: Linux version 6.5.0-generic
        Jan 01 12:00:01 hostname kernel: ACPI BIOS Error (bug): Could not resolve symbol
        Jan 01 12:00:01 hostname kernel: Additional error context line 1
        Jan 01 12:00:02 hostname kernel: Normal kernel message
        """
        
        with patch('acpi_bios_error.get_bios_info') as mock_bios_info:
            mock_bios_info.return_value = {
                'date': '01/15/2024',
                'release': '1.0.0', 
                'vendor': 'ACME Corp',
                'version': '1.2.3'
            }
            
            with self.assertRaises(SystemExit) as cm:
                check_acpi_bios_errors()
            
            self.assertEqual(str(cm.exception), "ACPI BIOS Error detected in kernel messages")

    @patch('acpi_bios_error.check_acpi_bios_errors')
    def test_main_no_errors(self, mock_check):
        """Test main function when no errors are found."""
        mock_check.return_value = None
        
        with patch('builtins.print') as mock_print:
            main()
            
        mock_print.assert_called_with("No ACPI BIOS errors detected in current boot")

    @patch('acpi_bios_error.check_acpi_bios_errors')
    def test_main_with_system_exit(self, mock_check):
        """Test main function when SystemExit is raised."""
        mock_check.side_effect = SystemExit("ACPI BIOS Error detected")
        
        with self.assertRaises(SystemExit):
            main()


if __name__ == '__main__':
    unittest.main()