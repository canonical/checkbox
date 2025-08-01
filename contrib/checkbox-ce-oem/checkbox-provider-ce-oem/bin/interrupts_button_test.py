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
from typing import List, Optional

# Define paths and constants
PROC_INTERRUPTS = "/proc/interrupts"
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
        """
        The self.irq_numbers will be store the mapping of IRQs for target
        interrupt name as a dict and assigned IRQ number as key only.
        self.irq_numbers = { IRQ_number1: None,
                             IRQ_number2: None }
        """
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
                """
                self.irq_numbers will be updated by assigning a list of
                affinity CPUs as the value for each IRQ accordingly.
                self.irq_numbers = { IRQ_number1: [0, 1],
                                     IRQ_number2: [3, 4] }
                """
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
            """
            counts will be a list of the numbers that from the output
            of /proc/interrupts. It will parse the line start with
            specific IRQ number and get the mulitple columes value
            which is depend on how many CPU cores for system.
            e.g. The output for /proc/interrupts as follows.
            count for IRQ number 1 will be count = [0, 0]

                    CPU0       CPU1
            1:          0          0     GICv3  25 Level     vgic
            3:    4341111    1892740     GICv3  30 Level     arch_timer
            """
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

        """
        Store initial counts for all monitored IRQs
        initial_counts_map = { IRQ_number1: [cpu0_count, cpu1_count, ...],
                               IRQ_number1: [cpu0_count, cpu1_count, ...] }
        """
        initial_counts_map = {}
        for irq in self.irq_numbers:
            counts = self._get_interrupt_counts(irq)
            if counts is None:
                logging.error("Failed to get initial counts for IRQ %d.", irq)
                return False  # Or raise an error
            initial_counts_map[irq] = counts

        logging.info("Initial interrupt counts on target CPUs:")
        """
        Following logic will mapping self.irq_numbers with initial_counts_map
        self.irq_numbers is a mapping of IRQ and affinity of CPUs.
        self.irq_numbers = { 132: [2,3],
                             144: [0,1] }
        initial_counts_map is a mapping of IRQ and the interrupt count of
        all CPUs
        initial_counts_map = { 132: [0, 0, 0, 0],
                               144: [2, 0, 4, 0] }
        """
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
            "The name of the interrupt source (e.g., 'gpio-keys') "
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
