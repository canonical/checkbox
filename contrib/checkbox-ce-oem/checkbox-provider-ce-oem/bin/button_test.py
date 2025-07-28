#!/usr/bin/env python3
"""
A script to monitor interrupts, verify IRQ CPU affinity, and test
interrupt triggers via GPIO or manual sysfs interaction.
"""

import argparse
import time
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

# Define paths and constants
PROC_INTERRUPTS = "/proc/interrupts"
GPIO_SYSFS_PATH = Path("/sys/class/gpio")
TEST_TIMEOUT = 30


class InterruptsTest:
    """
    This class finds IRQs for a device, gets their CPU affinities,
    and runs a test by monitoring for an increase in interrupt counts.
    It is designed to handle devices that may use multiple IRQ numbers.
    """

    def __init__(self, irq_name: str):
        """
        Args:
            irq_name: The name of the interrupt source (e.g., 'gpio-keys').
        """
        self.irq_name = irq_name
        # It maps each IRQ number to its list of target CPUs.
        # Example: {35: [0, 1], 36: [2, 3]}
        self.irq_numbers = {}
        self.num_cpus = os.cpu_count()

    def _get_irq_numbers(self) -> bool:
        """
        Finds all IRQ numbers for the given device name.

        Returns:
            True if at least one IRQ number was found, False otherwise.
        """
        logging.info(
            "Searching for IRQ name '%s' in %s...",
            self.irq_name,
            PROC_INTERRUPTS,
        )
        try:
            with open(PROC_INTERRUPTS, "r") as f:
                for line in f:
                    if self.irq_name in line:
                        parts = line.split()
                        irq_str = parts[0].strip().replace(":", "")
                        if irq_str.isdigit():
                            # Append every found IRQ number
                            self.irq_numbers[(int(irq_str))] = None

        except FileNotFoundError:
            logging.error("Proc file not found at %s.", PROC_INTERRUPTS)
            return False
        except Exception as e:
            logging.error("An error occurred while reading interrupts: %s", e)
            return False

        if not self.irq_numbers:
            logging.error(
                "Could not find any IRQ associated with %s.", self.irq_name
            )
            return False

        formatted_keys = ", ".join(str(k) for k in self.irq_numbers.keys())
        logging.info("Successfully found IRQ numbers: %s", formatted_keys)
        return True

    def _get_smp_affinities(self) -> bool:
        """
        Gets the list of CPU cores for each IRQ's affinity.

        Returns:
            True if affinities were determined for all IRQs, False otherwise.
        """
        for irq in self.irq_numbers.keys():
            affinity_file = "/proc/irq/{}/smp_affinity".format(irq)
            try:
                with open(affinity_file, "r") as f:
                    affinity_hex = f.read().strip()

                """
                The value in smp_affinity is the hex as a bitmask
                for the supported CPUs. For examples:
                The value in smp_affinity is 3, that makes the value
                of mask in binary is 0011. 0011 is mean the IRQ support
                CPU 0 and 1.

                Refer to https://docs.kernel.org/core-api/irq/irq-affinity.html
                for more detail.

                """
                affinity_mask = int(affinity_hex, 16)
                affected_cpus = [
                    cpu
                    for cpu in range(self.num_cpus)
                    if (affinity_mask >> cpu) & 1
                ]

                if not affected_cpus:
                    logging.warning(
                        "IRQ %d affinity mask '%s' targets no CPUs. "
                        "Defaulting to all CPUs for this IRQ.",
                        irq,
                        affinity_hex,
                    )
                    self.irq_numbers[irq] = list(range(self.num_cpus))
                else:
                    self.irq_numbers[irq] = affected_cpus

                logging.info(
                    "IRQ %d is tuned to run on CPU(s): %s",
                    irq,
                    self.irq_numbers[irq],
                )
            except Exception as e:
                logging.error(
                    "Error reading smp_affinity for IRQ %d: %s", irq, e
                )
                return False
        return True

    def _get_interrupt_counts(self, irq_number: int) -> Optional[List[int]]:
        """
        Gets current interrupt counts for a specific IRQ across all CPUs.

        Args:
            irq_number: The IRQ number to look for.

        Returns:
            A list of integer counts, or None on error.
        """
        try:
            with open(PROC_INTERRUPTS, "r") as f:
                for line in f:
                    # Match the line starting with the exact IRQ number
                    if line.strip().startswith("{}:".format(irq_number)):
                        parts = line.split()
                        # Get counts only for the number of available CPUs
                        max_idx = self.num_cpus + 1
                        counts = [
                            int(p) for p in parts[1:max_idx] if p.isdigit()
                        ]
                        return counts
        except Exception as e:
            logging.error(
                "Error reading interrupt counts for IRQ %d: %s",
                irq_number,
                e,
            )
        return None

    def run_test(self) -> bool:
        """
        Executes the full interrupt test. It succeeds if any of the monitored
        IRQs shows an increased interrupt count on any of its target CPUs.

        Returns:
            True if an interrupt was detected, False otherwise.
        """
        if not self._get_irq_numbers():
            raise RuntimeError(
                "Could not find IRQs for '{}'.".format(self.irq_name)
            )

        if not self._get_smp_affinities():
            raise RuntimeError("Could not get CPU affinities for all IRQs.")

        # Store initial counts for all monitored IRQs
        initial_counts_map = {}
        for irq in self.irq_numbers:
            counts = self._get_interrupt_counts(irq)
            if counts is None:
                logging.error("Failed to get initial counts for IRQ %d.", irq)
                return False  # Or raise an error
            initial_counts_map[irq] = counts

        logging.info("Initial interrupt counts on target CPUs:")
        for irq, cpus in self.irq_numbers.items():
            for cpu in cpus:
                logging.info(
                    "IRQ %d, CPU %d: %d",
                    irq,
                    cpu,
                    initial_counts_map[irq][cpu],
                )

        logging.info(
            "Monitoring for interrupt activity for %d seconds...",
            TEST_TIMEOUT,
        )
        for _ in range(TEST_TIMEOUT):
            # Check each IRQ for an increase in counts
            for irq_num, target_cpus in self.irq_numbers.items():
                current_counts = self._get_interrupt_counts(irq_num)
                if not current_counts:
                    continue  # Skip if we failed to read counts

                initial_counts = initial_counts_map[irq_num]
                for cpu in target_cpus:
                    if current_counts[cpu] > initial_counts[cpu]:
                        logging.info(
                            "SUCCESS: Interrupt detected on IRQ %d (CPU %d)!",
                            irq_num,
                            cpu,
                        )
                        logging.info(
                            "Initial count: %d, Final count: %d",
                            initial_counts[cpu],
                            current_counts[cpu],
                        )
                        return True
            time.sleep(1)

        logging.error(
            "TEST FAILED: No interrupt activity detected on any "
            "monitored IRQ/CPU pair for %s.",
            self.irq_name,
        )
        return False


class GpioTest:
    """
    A class to test a GPIO button press using a context manager.

    This class checks if the GPIO pin is already exported. It will only
    unexport the pin on exit if it was the one to export it initially,
    preventing interference with other processes.
    """

    def __init__(self, name: str, gpio_pin: str):
        """
        Initializes the GPIOTest.

        Args:
            name: The name of the button.
            gpio_pin: The GPIO pin number to test.
        """
        self.name = name
        self.gpio_pin = gpio_pin
        self.gpio_node = GPIO_SYSFS_PATH / "gpio{}".format(self.gpio_pin)
        self._was_exported_before = False
        logging.info("Initialized test for '%s' on GPIO %s", name, gpio_pin)

    def __enter__(self):
        """
        Enter the runtime context and set up the GPIO pin.

        This method checks the initial export state, then exports and
        configures the GPIO pin for input if necessary.

        Returns:
            The instance of the class (self).

        Raises:
            IOError: If the GPIO setup fails.
        """
        logging.info("--- Entering context: Setting up GPIO ---")
        # Monitor the initial state BEFORE any setup actions.
        self._was_exported_before = self.gpio_node.exists()
        if self._was_exported_before:
            logging.info(
                "GPIO %s was already exported. Will not unexport on exit.",
                self.gpio_pin,
            )

        if not self._setup_gpio():
            # Raise an error to prevent the 'with' block from executing
            raise IOError("Failed to set up GPIO {}".format(self.gpio_pin))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit the runtime context and clean up the GPIO pin.

        This method unexports the GPIO pin only if it wasn't
        exported before this context was entered.
        """
        logging.info("--- Exiting context: Cleaning up GPIO ---")
        # Only unexport if the pin was not already exported.
        if not self._was_exported_before and self.gpio_node.exists():
            try:
                logging.info(
                    "Unexporting GPIO %s (we exported it)...", self.gpio_pin
                )
                (GPIO_SYSFS_PATH / "unexport").write_text(str(self.gpio_pin))
            except Exception as e:
                logging.error(
                    "Failed to unexport GPIO %s: %s", self.gpio_pin, e
                )
        else:
            logging.info(
                "Leaving GPIO %s exported as it was found.", self.gpio_pin
            )

    def _setup_gpio(self) -> bool:
        """
        Exports (if needed) and configures the GPIO pin.

        Returns:
            True on success, False on failure.
        """
        # The export logic is now conditional on the node's existence.
        if not self.gpio_node.exists():
            logging.info("Exporting GPIO %s to system...", self.gpio_pin)
            try:
                (GPIO_SYSFS_PATH / "export").write_text(str(self.gpio_pin))
                time.sleep(1)  # Give sysfs time to create the node
            except Exception as e:
                logging.error("Error exporting GPIO %s: %s", self.gpio_pin, e)
                return False

        if not self.gpio_node.is_dir():
            logging.error("Unable to access GPIO %s.", self.gpio_pin)
            return False

        try:
            direction_file = self.gpio_node / "direction"
            if direction_file.read_text(encoding="utf-8").strip() != "in":
                direction_file.write_text("in")
            logging.info("Set GPIO %s direction to 'in'", self.gpio_pin)
        except Exception as e:
            logging.error(
                "Error setting direction for GPIO %s: %s", self.gpio_pin, e
            )
            return False

        return True

    def run_test(self) -> bool:
        """
        Prompts user to press/release button and checks GPIO state.

        This should be called inside the 'with' block after the
        GPIO has been successfully set up.

        Returns:
            True if press and release are detected, False otherwise.
        """
        try:
            initial_value = (self.gpio_node / "value").read_text().strip()
            logging.info(
                "Initial value of %s is: %s",
                self.gpio_node.name,
                "High" if initial_value == "1" else "Low",
            )

            # Test Press
            logging.info("Please PRESS and HOLD the '%s' button...", self.name)
            for _ in range(TEST_TIMEOUT):
                val = (self.gpio_node / "value").read_text().strip()
                if val != initial_value:
                    logging.info("PASS: Button press detected!")
                    break
                time.sleep(1)
            else:
                logging.error("FAIL: No button press detected.")
                return False

            # Test Release
            logging.info("Please RELEASE the '%s' button...", self.name)
            for _ in range(TEST_TIMEOUT):
                val = (self.gpio_node / "value").read_text().strip()
                if val == initial_value:
                    logging.info("PASS: Button release detected!")
                    return True
                time.sleep(1)
            else:
                logging.error("FAIL: No button release detected.")
                return False

        except Exception as e:
            logging.error("An error occurred during GPIO test: %s", e)
            return False


def parse_arguments() -> argparse.Namespace:
    """
    Parses and validates command-line arguments.

    Returns:
        The populated argparse.Namespace object.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Monitor interrupts, verify IRQ CPU affinity, and "
            "optionally test a GPIO button."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "type",
        choices=["interrupts", "gpio"],
        help="The testing types in 'interrupts' and 'gpio' button.",
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help=(
            "The name of the interrupt source (e.g., 'gpio-keys') "
            "to find in /proc/interrupts. "
            "Or a GPIO button name"
        ),
    )
    parser.add_argument(
        "--gpio-pin",
        type=str,
        help="The GPIO pin number (required for 'gpio' type test).",
    )

    args = parser.parse_args()
    if args.type == "gpio" and args.gpio_pin is None:
        parser.error("--gpio-pin is required when type is 'gpio'")

    return args


def main():
    """Main function to orchestrate the interrupt test."""
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", stream=sys.stdout
    )

    if os.geteuid() != 0:
        logging.error(
            "This script needs root privileges to access sysfs and /proc."
        )
        sys.exit(1)

    args = parse_arguments()
    test_result = None

    if args.type == "gpio":
        button_test = GpioTest(name=args.name, gpio_pin=args.gpio_pin)
        with button_test as test:
            test_result = test.run_test()
    elif args.type == "interrupts":
        button_test = InterruptsTest(irq_name=args.name)
        test_result = button_test.run_test()

    if test_result:
        logging.info("Button Test for '%s' PASSED!", args.name)
    else:
        logging.error("Button Test for '%s' FAILED!", args.name)
        sys.exit(1)


if __name__ == "__main__":
    main()
