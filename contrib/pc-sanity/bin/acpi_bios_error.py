#!/usr/bin/env python3

import subprocess


def print_bios_info():
    """Print BIOS information from DMI fields."""
    dmi_fields = {
        "date": "/sys/class/dmi/id/bios_date",
        "release": "/sys/class/dmi/id/bios_release",
        "vendor": "/sys/class/dmi/id/bios_vendor",
        "version": "/sys/class/dmi/id/bios_version",
    }

    for field, path in dmi_fields.items():
        try:
            with open(path, "r") as f:
                value = f.read().strip()
        except (OSError, IOError) as e:
            value = f"Unable to read {path}: {e}"

        print(f"BIOS {field}: {value}")


def check_acpi_bios_errors():
    """
    Check for ACPI BIOS errors in the current boot's kernel messages.
    Raises SystemExit if errors are found.
    """
    journal = subprocess.check_output(
        ["journalctl", "-b", "-k"],
        universal_newlines=True,
        stderr=subprocess.STDOUT,
    )

    lines = journal.splitlines()
    acpi_error_lines = []
    for i, line in enumerate(lines):
        if "ACPI BIOS Error" in line:
            acpi_error_lines.append(i)

    if acpi_error_lines:
        # Mimic grep -A 20: error line + 20 lines after it
        picked_lines = set()
        output_lines = []
        last_added = -1

        for error_line in acpi_error_lines:
            # Add separator when next error outside of 20 lines context
            if output_lines and error_line > last_added + 1:
                output_lines.append("------")

            for j in range(error_line, min(error_line + 21, len(lines))):
                # Track picked lines to avoid duplicates if next error
                # within 20 lines context
                if j not in picked_lines:
                    picked_lines.add(j)
                    output_lines.append(lines[j])
                    last_added = j
        print("!!! ACPI BIOS Error detected !!!")
        print_bios_info()
        for error_line in output_lines:
            print(error_line)

        raise SystemExit("ACPI BIOS Error detected in kernel messages")


def main():
    check_acpi_bios_errors()
    print("No ACPI BIOS errors detected in current boot")


if __name__ == "__main__":
    main()
