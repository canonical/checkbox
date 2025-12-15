import unittest
from unittest.mock import patch, mock_open
import subprocess

from acpi_bios_error import check_acpi_bios_errors, main


class TestAcpiBiosError(unittest.TestCase):

    @patch("subprocess.check_output")
    def test_check_acpi_bios_errors_no_errors(self, mock_subprocess):
        """Test when no ACPI BIOS errors are found."""
        mock_subprocess.return_value = """Sep 18 17:17:37 test-host kernel: ACPI: 28 ACPI AML tables successfully acquired and loaded
Sep 18 17:17:37 test-host kernel: ACPI Error: No pointer back to namespace node in package (___ptrval___) (20240827/dsargs-301)
Sep 18 17:17:37 test-host kernel: ACPI Error: No pointer back to namespace node in package (___ptrval___) (20240827/dsargs-301)
Sep 18 17:17:37 test-host kernel: ACPI: EC: EC started
Sep 18 17:17:37 test-host kernel: ACPI: EC: interrupt blocked
Sep 18 17:17:37 test-host kernel: ACPI: EC: EC_CMD/EC_SC=0x66, EC_DATA=0x62
Sep 18 17:17:37 test-host kernel: ACPI: EC: Boot ECDT EC used to handle transactions
Sep 18 17:17:37 test-host kernel: ACPI: [Firmware Bug]: BIOS _OSI(Linux) query ignored
Sep 18 17:17:37 test-host kernel: ACPI: USB4 _OSC: OS supports USB3+ DisplayPort+ PCIe+ XDomain+
Sep 18 17:17:37 test-host kernel: ACPI: USB4 _OSC: OS controls USB3+ DisplayPort+ PCIe+ XDomain+"""

        check_acpi_bios_errors()
        mock_subprocess.assert_called_once_with(
            ["journalctl", "-b", "-k"],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )

    @patch("acpi_bios_error.print_bios_info")
    @patch("subprocess.check_output")
    def test_check_acpi_bios_errors_found(self, mock_subprocess, mock_print_bios):
        """Test when ACPI BIOS errors are detected."""
        mock_subprocess.return_value = """Sep 18 17:17:37 test-host kernel: ACPI BIOS Error (bug): Failure creating named object [_SB.PC00.TXHC.RHUB.SS01._UPC], AE_ALREADY_EXISTS (20240827/dswload2-326)
Sep 18 17:17:37 test-host kernel: ACPI Error: AE_ALREADY_EXISTS, During name lookup/catalog (20240827/psobject-220)
Sep 18 17:17:37 test-host kernel: ACPI: Skipping parse of AML opcode: Method (0x0014)
Sep 18 17:17:37 test-host kernel: ACPI BIOS Error (bug): Failure creating named object [_SB.PC00.TXHC.RHUB.SS01._PLD], AE_ALREADY_EXISTS (20240827/dswload2-326)
Sep 18 17:17:37 test-host kernel: ACPI Error: AE_ALREADY_EXISTS, During name lookup/catalog (20240827/psobject-220)
Sep 18 17:17:37 test-host kernel: ACPI: Skipping parse of AML opcode: Method (0x0014)
Sep 18 17:17:37 test-host kernel: ACPI BIOS Error (bug): Could not resolve symbol [_SB.PC02.RP21.PXSX.TBDU.XHCI.RHUB.SS01], AE_NOT_FOUND (20240827/dswload2-162)
Sep 18 17:17:37 test-host kernel: ACPI Error: AE_NOT_FOUND, During name lookup/catalog (20240827/psobject-220)
Sep 18 17:17:37 test-host kernel: ACPI: Skipping parse of AML opcode: Scope (0x0010)
Sep 18 17:17:37 test-host kernel: ACPI: 28 ACPI AML tables successfully acquired and loaded"""

        with self.assertRaises(SystemExit):
            check_acpi_bios_errors()


if __name__ == "__main__":
    unittest.main()
