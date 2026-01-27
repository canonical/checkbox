#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang    <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

"""
CPU Idle State Trigger Test - Python Implementation

This script replicates the FWTS cpuidle test functionality to trigger
all available CPU idle states on each processor by creating alternating
load patterns that allow the idle governor to discover and use all states.

Author: Based on FWTS cstates.c implementation
License: GPL-2.0+

Usage:
    sudo python3 cpu_idle_state.py [--verbose]

Examples:
    sudo python3 cpu_idle_state_fwts.py
    sudo python3 cpu_idle_state_fwts.py --verbose
"""

import os
import sys
import time
import math
import glob
import logging
from typing import Dict, List
import psutil
import argparse


class IdleState:
    """Represents a CPU idle state"""

    def __init__(
        self,
        name: str,
        number: int,
        usage_count: int,
        used: bool = False,
        logged: bool = False,
    ) -> None:
        self.name = name
        self.number = number
        self.usage_count = usage_count
        self.used = used
        self.logged = logged


class CpuIdleInfo:
    """CPU idle information for a specific CPU"""

    def __init__(
        self,
        cpu_id: int,
        states: Dict[int, IdleState],
        path: str,
    ) -> None:
        self.cpu_id = cpu_id
        self.states = states
        self.path = path


class CpuAffinityError(Exception):
    """Exception raised when CPU affinity operations fail"""

    pass


class Logger:
    """Custom logger class for CPU idle state testing"""

    def __init__(self, verbose: bool = False):
        """Initialize logger with specified verbosity level"""
        self.verbose = verbose
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="[%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)


class CpuBenchmark:
    """CPU benchmarking functionality"""

    def __init__(self, logger: Logger):
        """Initialize CPU benchmark with logger"""
        self.logger = logger

    def get_cpu_affinity(self) -> List[int]:
        """Get current CPU affinity"""
        try:
            return psutil.Process().cpu_affinity()
        except psutil.AccessDenied:
            msg = "Cannot get CPU affinity - need root privileges"
            raise CpuAffinityError(msg)

    def set_cpu_affinity(self, cpu_id: List[int]) -> None:
        """Set CPU affinity to a list of CPUs"""
        try:
            psutil.Process().cpu_affinity(cpu_id)
        except psutil.AccessDenied:
            msg = "Cannot set CPU affinity - need root privileges"
            raise CpuAffinityError(msg)

    def restore_cpu_affinity(self, affinity: List[int]) -> None:
        """Restore CPU affinity to previous setting"""
        self.set_cpu_affinity(affinity)

    def burn_cpu_cycles(self):
        """
        Burn CPU cycles similar to FWTS fwts_cpu_burn_cycles().
        It use the floating point operations to burn CPU cycles.
        """
        a = 1.234567
        b = 3.121213

        for _ in range(100):
            a = a * b
            b = a * a
            # Ensure a is positive before taking square root
            a = a - b + math.sqrt(abs(a))
            a = a * b
            b = a * a
            a = a - b + math.sqrt(abs(a))
            a = a * b
            b = a * a
            a = a - b + math.sqrt(abs(a))
            a = a * b
            b = a * a
            a = a - b + math.sqrt(abs(a))

    def cpu_benchmark(self, cpu_id: int) -> float:
        """Run CPU benchmark on specific CPU, similar to FWTS
        fwts_cpu_benchmark()
        It will burn CPU cycles for ~250ms.
        """
        # Set CPU affinity
        old_affinity = self.get_cpu_affinity()
        self.set_cpu_affinity([cpu_id])

        try:
            start_time = time.time()
            loops = 0

            # Run benchmark for ~250ms (same as FWTS)
            while (time.time() - start_time) < 0.25:
                self.burn_cpu_cycles()
                loops += 1

            duration = time.time() - start_time
            return loops / duration if duration > 0 else 0

        finally:
            # Restore CPU affinity
            self.restore_cpu_affinity(old_affinity)


class CpuIdleTest:
    """Main class for CPU idle state testing"""

    PROCESSOR_PATH = "/sys/devices/system/cpu"
    TOTAL_WAIT_TIME = 20  # Same as FWTS

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.cpus = []
        self.state_count = -1
        self.first_cpu = -1
        self.logger = Logger(verbose)
        self.benchmark = CpuBenchmark(self.logger)

    def get_cpu_count(self) -> int:
        """Get the number of CPUs in the system"""
        return psutil.cpu_count(logical=True)

    def get_cpuidle_states(self, cpu_path: str) -> Dict[int, IdleState]:
        """Get current CPU idle states, similar to FWTS get_cpuidle_states()"""
        states = {}

        try:
            # Find all state directories
            state_dirs = glob.glob("{}/*".format(cpu_path))

            for state_dir in state_dirs:
                state_name = os.path.basename(state_dir)

                # Parse state number (state0, state1, etc.)
                if state_name.startswith("state"):
                    try:
                        # Extract number after "state"
                        state_num = int(state_name[5:])
                    except ValueError:
                        continue

                    # Read state name
                    name_file = os.path.join(state_dir, "name")
                    try:
                        with open(name_file, "r") as f:
                            state_name_str = f.read().strip()
                    except (IOError, OSError):
                        state_name_str = "state{}".format(state_num)

                    # Read usage count
                    usage_file = os.path.join(state_dir, "usage")
                    try:
                        with open(usage_file, "r") as f:
                            usage_count = int(f.read().strip())
                    except (IOError, OSError, ValueError):
                        usage_count = 0

                    states[state_num] = IdleState(
                        name=state_name_str,
                        number=state_num,
                        usage_count=usage_count,
                    )

        except (IOError, OSError) as e:
            self.logger.error(
                "Error reading CPU idle states from {}: {}".format(cpu_path, e)
            )

        return states

    def discover_cpus(self) -> List[CpuIdleInfo]:
        """Discover all CPUs with cpuidle support"""
        cpus = []

        # Get number of CPUs
        cpu_count = self.get_cpu_count()
        self.logger.info("Found {} CPUs in system".format(cpu_count))

        # Check each CPU for cpuidle support
        for cpu_id in range(cpu_count):
            cpu_path = "{}/cpu{}/cpuidle".format(self.PROCESSOR_PATH, cpu_id)

            if os.path.exists(cpu_path):
                states = self.get_cpuidle_states(cpu_path)
                if states:
                    cpu_info = CpuIdleInfo(
                        cpu_id=cpu_id,
                        states=states,
                        path=cpu_path,
                    )
                    cpus.append(cpu_info)
                    self.logger.info(
                        "CPU {}: Found {} idle states".format(
                            cpu_id,
                            len(states),
                        )
                    )
                else:
                    msg = "CPU {}: No idle states found".format(cpu_id)
                    self.logger.warning(msg)
            else:
                self.logger.debug("CPU {}: No cpuidle support".format(cpu_id))

        return cpus

    def test_cpu_idle_states(
        self, cpu_info: CpuIdleInfo, cpu_index: int, total_cpus: int
    ):
        """Test idle states for a specific CPU, similar to FWTS do_cpu()"""
        self.logger.info(
            "Testing CPU {} ({}/{})".format(
                cpu_info.cpu_id,
                cpu_index + 1,
                total_cpus,
            )
        )

        # Get initial state
        initial_states = self.get_cpuidle_states(cpu_info.path)
        current_states = initial_states.copy()

        # Track which states have been used and store original usage counts
        original_usage_counts = {}
        for state_num in initial_states:
            initial_states[state_num].used = False
            original_usage_counts[state_num] = initial_states[
                state_num
            ].usage_count

        keep_going = True

        for iteration in range(self.TOTAL_WAIT_TIME):
            if not keep_going:
                break

            # Report progress
            if iteration % 3 == 0:
                progress = (
                    100
                    * (iteration + (self.TOTAL_WAIT_TIME * cpu_index))
                    / (total_cpus * self.TOTAL_WAIT_TIME)
                )
                self.logger.debug(
                    "CPU {} progress: {:.1f}% (iteration {}/{})".format(
                        cpu_info.cpu_id,
                        progress,
                        iteration + 1,
                        self.TOTAL_WAIT_TIME,
                    )
                )

            # Alternate between sleep and benchmark (same pattern as FWTS)
            if (iteration & 7) < 4:
                # Sleep phase - allow CPU to go idle
                time.sleep(1)
            else:
                # Benchmark phase - create CPU load
                try:
                    result = self.benchmark.cpu_benchmark(cpu_info.cpu_id)
                    if self.verbose:
                        self.logger.debug(
                            "CPU {} benchmark: {:.0f} loops/sec".format(
                                cpu_info.cpu_id,
                                result,
                            )
                        )
                except CpuAffinityError as e:
                    self.logger.error(
                        "CPU {} benchmark failed: {}".format(
                            cpu_info.cpu_id,
                            e,
                        )
                    )

            # Check for state changes
            current_states = self.get_cpuidle_states(cpu_info.path)

            keep_going = False
            for state_num in initial_states:
                if state_num in current_states:
                    if (
                        initial_states[state_num].usage_count
                        != current_states[state_num].usage_count
                    ):
                        # State was used
                        initial_states[state_num].usage_count = current_states[
                            state_num
                        ].usage_count
                        initial_states[state_num].used = True

                        # Log based on whether this state has been
                        # logged before
                        if not initial_states[state_num].logged:
                            # First time reaching this state - use info level
                            self.logger.info(
                                "CPU {}: State {} ({}) was used".format(
                                    cpu_info.cpu_id,
                                    state_num,
                                    initial_states[state_num].name,
                                )
                            )
                            initial_states[state_num].logged = True
                        else:
                            # Subsequent times reaching this state - use
                            # debug level
                            self.logger.debug(
                                "CPU {}: State {} ({}) was used again".format(
                                    cpu_info.cpu_id,
                                    state_num,
                                    initial_states[state_num].name,
                                )
                            )

                    if not initial_states[state_num].used:
                        keep_going = True

            # Early termination if all states reached
            if not keep_going:
                self.logger.info(
                    "CPU {}: All idle states reached, stopping early".format(
                        cpu_info.cpu_id
                    )
                )
                break

        # Report results
        used_states = [s for s in initial_states.values() if s.used]

        # Check for states that didn't increase but had non-zero original usage
        states_with_notes = []
        failed_states = []

        for state_num, state in initial_states.items():
            if not state.used:
                original_usage = original_usage_counts[state_num]
                if original_usage > 0:
                    # State didn't increase but had non-zero original usage
                    # - pass with note
                    states_with_notes.append(state.name)
                else:
                    # State didn't increase and had zero original usage - fail
                    failed_states.append(state.name)

        if failed_states:
            # These states failed the test
            self.logger.warning(
                "CPU {}: WARNING - States not reached: {}".format(
                    cpu_info.cpu_id, ", ".join(failed_states)
                )
            )

        if states_with_notes:
            # These states pass but with a note
            self.logger.info(
                "CPU {}: NOTE - ".format(cpu_info.cpu_id)
                + "States with existing usage (not tested): {}".format(
                    ", ".join(states_with_notes),
                )
            )

        if not failed_states and not states_with_notes:
            # All states were used
            used_names = ["{}".format(state.name) for state in used_states]
            self.logger.info(
                "CPU {}: SUCCESS - All states reached: {}".format(
                    cpu_info.cpu_id, ", ".join(used_names)
                )
            )

        # Check state count consistency
        state_count = len(initial_states)
        if self.state_count == -1:
            self.state_count = state_count
        elif self.state_count != state_count:
            self.logger.error(
                "CPU {}: ERROR - Expected {} states, found {}".format(
                    cpu_info.cpu_id, self.state_count, state_count
                )
            )
        else:
            if self.first_cpu == -1:
                self.first_cpu = cpu_info.cpu_id
            else:
                self.logger.debug(
                    "CPU {}: State count matches CPU {}".format(
                        cpu_info.cpu_id, self.first_cpu
                    )
                )

        return len(failed_states) == 0

    def run_test(self) -> bool:
        """Run the complete CPU idle state test"""
        self.logger.info("Starting CPU idle state test")
        self.logger.info(
            "This test checks if all processors have the same number of "
            "idle states and if idle state transitions happen during "
            "alternating load patterns"
        )

        # Discover CPUs
        self.cpus = self.discover_cpus()

        if not self.cpus:
            self.logger.error("ERROR: No CPUs with cpuidle support found")
            return False
        msg = "Testing {} CPUs with cpuidle support".format(len(self.cpus))
        self.logger.info(msg)

        # Test each CPU
        success_count = 0
        for i, cpu_info in enumerate(self.cpus):
            try:
                if self.test_cpu_idle_states(cpu_info, i, len(self.cpus)):
                    success_count += 1
            except Exception as e:
                msg = "ERROR testing CPU {}: {}".format(cpu_info.cpu_id, e)
                self.logger.error(msg)

        # Final report
        self.logger.info(
            "\nTest completed: {}/{} CPUs passed".format(
                success_count,
                len(self.cpus),
            )
        )

        if success_count == len(self.cpus):
            self.logger.info("SUCCESS: All CPUs reached all their idle states")
            return True
        else:
            self.logger.error("ERROR: Some CPUs did not reach all idle states")
            return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="CPU Idle State Trigger Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run test with verbose output
  sudo python3 cpu_idle_test.py --verbose

  # Run test silently (only errors/warnings)
  sudo python3 cpu_idle_test.py

  # Run test and save output to file
  sudo python3 cpu_idle_test.py --verbose 2>&1 | tee cpu_idle_test.log
        """,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    # Check if running as root
    if os.geteuid() != 0:
        print(
            "ERROR: This script must be run as root (sudo) to set CPU "
            "affinity\n"
            "Usage: sudo python3 cpu_idle_state_fwts.py [--verbose]"
        )
        sys.exit(1)

    # Run the test
    test = CpuIdleTest(verbose=args.verbose)

    try:
        success = test.run_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print("ERROR: {}".format(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
