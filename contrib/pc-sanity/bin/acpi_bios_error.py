#!/usr/bin/env python3

import subprocess
import sys


def get_bios_info():
    """
    Collect BIOS information from DMI sysfs interface.
    Returns a dictionary with BIOS details.
    """
    bios_info = {}
    dmi_fields = {
        'date': '/sys/class/dmi/id/bios_date',
        'release': '/sys/class/dmi/id/bios_release',
        'vendor': '/sys/class/dmi/id/bios_vendor',
        'version': '/sys/class/dmi/id/bios_version'
    }

    for field, path in dmi_fields.items():
        try:
            with open(path, 'r') as f:
                bios_info[field] = f.read().strip()
        except (OSError, IOError) as e:
            bios_info[field] = f"Unable to read {path}: {e}"

    return bios_info


def check_acpi_bios_errors():
    """
    Check for ACPI BIOS errors in the current boot's kernel messages.
    Raises SystemExit if errors are found.
    """
    try:
        # Get kernel messages from current boot
        journal = subprocess.check_output(
            ["journalctl", "-b", "-k"],
            universal_newlines=True,
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running journalctl: {e}", file=sys.stderr)
        return

    # Look for ACPI BIOS Error patterns
    acpi_errors = []
    lines = journal.splitlines()

    for i, line in enumerate(lines):
        if "ACPI BIOS Error" in line:
            # Collect the error line and up to 20 following lines for context
            error_context = [line]
            for j in range(i + 1, min(i + 21, len(lines))):
                error_context.append(lines[j])
            acpi_errors.extend(error_context)
            acpi_errors.append("")  # Add blank line between error blocks

    if acpi_errors:
        # Get BIOS information for diagnostics
        bios_info = get_bios_info()

        print("!!! ACPI BIOS Error detected !!!")
        print(f"BIOS date: {bios_info['date']}")
        print(f"BIOS release: {bios_info['release']}")
        print(f"BIOS vendor: {bios_info['vendor']}")
        print(f"BIOS version: {bios_info['version']}")
        print()
        print("ACPI BIOS Error details:")
        for error_line in acpi_errors:
            print(error_line)

        raise SystemExit("ACPI BIOS Error detected in kernel messages")


def main():
    """Main function to run ACPI BIOS error check."""
    try:
        check_acpi_bios_errors()
        print("No ACPI BIOS errors detected in current boot")
    except SystemExit:
        # Re-raise SystemExit to maintain error code
        raise
    except Exception as e:
        error_msg = f"Unexpected error during ACPI BIOS error check: {e}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
