#!/usr/bin/env python3
"""
A script to monitor interrupts, verify IRQ CPU affinity, and test
interrupt triggers via manual sysfs interaction.
"""

import argparse
import time
import os
import sys
import logging
from typing import List, Optional

# Define paths and constants
PROC_INTERRUPTS = "/proc/interrupts"
TEST_TIMEOUT = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class InterruptsTest:
    """
    This class finds IRQs for a device, gets their CPU affinities,
    and runs a test by monitoring for an increase in interrupt counts.
    It is designed to handle devices that may use multiple IRQ numbers.
    """

    def __init__(self, irq_name: str):
        """
        Args:
            irq_name: The name of the interrupt source (e.g., 'test-keys').
        """
        self.irq_name = irq_name
        # It maps each IRQ number to its list of target CPUs.
        # Example: {35: [0, 1], 36: [2, 3]}
        self.irq_numbers = {}
        self.num_cpus = os.cpu_count()

    def _get_irq_numbers_counts(self) -> bool:
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
        """
        Following logic will mapping self.irq_numbers with initial_counts_map
        initial_counts_map is a mapping of IRQ and the interrupt count of
        all CPUs
        initial_counts_map = { 132: [0, 0, 0, 0],
                               144: [2, 0, 4, 0] }
        """
        try:
            with open(PROC_INTERRUPTS, "r") as f:
                for line in f:
                    if self.irq_name in line:
                        parts = line.split()
                        # looking for irq_number for matching irq_name
                        irq_str = parts[0].strip().replace(":", "")
                        # Get max CPU index. The index start from 0.
                        max_idx = self.num_cpus + 1
                        # Get interrupts count for each CPU.
                        counts = [
                            int(p) for p in parts[1:max_idx] if p.isdigit()
                        ]
                        if irq_str.isdigit():
                            # Append every found IRQ number
                            self.irq_numbers[(int(irq_str))] = counts
                        else:
                            logging.error(line)
                            raise ValueError("Can't found IRQ number by name!")
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
        return self.irq_numbers

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
                affected_cpus will be a list include the affected cpu core for
                the irq.
                """
                affinity_mask = int(affinity_hex, 16)
                affected_cpus = {
                    cpu
                    for cpu in range(self.num_cpus)
                    if (affinity_mask >> cpu) & 1
                }
                logging.info(
                    "IRQ %d affinity mask '%s' targets CPU(s): %s",
                    irq,
                    affinity_hex,
                    affected_cpus,
                )
                return affected_cpus
            except Exception as e:
                raise SystemError(
                    "Error reading smp_affinity for IRQ %d: %s", irq, e
                )

    def run_test(self) -> bool:
        """
        Executes the full interrupt test. It succeeds if any of the monitored
        IRQs shows an increased interrupt count on any of its target CPUs.

        Returns:
            True if an interrupt was detected, False otherwise.
        """

        """
        Store initial counts for all monitored IRQs
        initial_counts = { IRQ_number1: [cpu0_count, cpu1_count, ...],
                           IRQ_number2: [cpu0_count, cpu1_count, ...] }
        """
        initial_counts = self._get_irq_numbers_counts()
        if not initial_counts:
            raise RuntimeError(
                "Could not find IRQs for '{}'.".format(self.irq_name)
            )
        affected_cpus = self._get_smp_affinities()
        logging.info("Initial interrupt counts on target CPUs:")
        for irq, cpus in initial_counts.items():
            logging.info("IRQ %d, CPU counts %s", irq, cpus)

        logging.info(
            "Monitoring for interrupt activity for %d seconds...",
            TEST_TIMEOUT,
        )
        for _ in range(TEST_TIMEOUT):
            current_counts = self._get_irq_numbers_counts()
            if not current_counts:
                continue  # Skip if we failed to read counts
            # Compare current counts to initial counts
            # If any target CPU shows an increase, the test passes
            for irq_num in current_counts.keys():
                # Check if there is any change in interrupt counts
                if current_counts[irq_num] != initial_counts[irq_num]:
                    for indesx, value in enumerate(current_counts[irq_num]):
                        if value != initial_counts[irq_num][indesx]:
                            if indesx in affected_cpus:
                                logging.info(
                                    "SUCCESS: Interrupt detected on IRQ %d!",
                                    irq_num,
                                )
                                logging.info(
                                    "Initial count: %s, Final count: %s",
                                    initial_counts,
                                    current_counts,
                                )
                                return True
            time.sleep(3)

        logging.error(
            "TEST FAILED: No interrupt activity detected on any "
            "monitored IRQ/CPU pair for %s.",
            self.irq_name,
        )
        return False


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor interrupts, verify IRQ CPU affinity "
            "for testing a interrupts button."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help=(
            "The name of the interrupt source (e.g., 'test-keys') "
            "to find in /proc/interrupts. "
        ),
    )

    args = parser.parse_args()
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
    button_test = InterruptsTest(irq_name=args.name)
    test_result = button_test.run_test()

    if test_result:
        logging.info("Button Test for '%s' PASSED!", args.name)
    else:
        logging.error("Button Test for '%s' FAILED!", args.name)
        sys.exit(1)


if __name__ == "__main__":
    main()
