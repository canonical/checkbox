#!/usr/bin/env python3

import argparse
import logging
import os
import re
import subprocess
import sys
import time

from multiprocessing import cpu_count
from typing import List


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


class CPUScalingInfo:
    """A class for gathering CPU scaling information."""

    def __init__(self, policy=0):
        """
        Initialize the CPUScalingInfo object.

        Args:
            policy (int): The CPU policy number to be used (default is 0).
        """
        self.sys_cpu_dir = "/sys/devices/system/cpu"
        self.policy = policy
        self.cpu_policies = self.get_cpu_policies()
        self.min_freq = self.get_min_frequency()
        self.max_freq = self.get_max_frequency()
        self.governors = self.get_supported_governors()
        self.original_governor = self.get_governor()
        self.affected_cpus = self.get_affected_cpus()

    def get_cpu_policies(self) -> List:
        """
        Get a list of available CPU policies.

        Returns:
            List: A sorted list of available CPU policy numbers.
        """
        path = os.path.join(self.sys_cpu_dir, "cpufreq")
        try:
            policies = [
                int(policy[6:])
                for policy in os.listdir(path)
                if re.match(r"policy\d+", policy)
            ]
        except IOError:
            print("ERROR: Failed to get CPU policies from {}".format(path))
            return []
        if not policies:
            print("ERROR: No CPU policies found in {}".format(path))
            return []
        return sorted(policies)

    def get_scaling_driver(self, policy=0) -> str:
        """
        Get the scaling driver used by a specific CPU policy.

        Args:
            policy (int): The CPU policy number to query (default is 0).

        Returns:
            str: The name of the scaling driver for the specified policy.
        """
        path = os.path.join(
            self.sys_cpu_dir,
            "cpufreq",
            "policy{}".format(policy),
            "scaling_driver",
        )
        try:
            with open(path, "r") as attr_file:
                line = attr_file.read()
                return line.strip()
        except IOError:
            print("ERROR: Fail to get scaling driver from {}".format(path))
            return ""

    def print_policies_list(self) -> bool:
        """
        Print the list of CPU policies and their corresponding scaling drivers

        The output is in Checkbox resource job format.

        Returns:
            bool: True if the list is printed successfully, False otherwise.
        """
        if not self.cpu_policies:
            return False
        for policy in self.cpu_policies:
            driver = self.get_scaling_driver(policy)
            print("policy: {}".format(policy))
            print("scaling_driver: {}".format(driver))
            print()
        return True

    def get_attribute(self, attr) -> str:
        """
        Get the value of a specific attribute from the CPU sysfs.

        Args:
            attr (str): The name of the attribute to query.

        Returns:
            str: The value of the specified attribute.
        """
        logging.debug("Getting value from attribute '%s'", attr)
        path = os.path.join(self.sys_cpu_dir, attr)
        try:
            with open(path, "r") as attr_file:
                line = attr_file.read()
                return line.strip()
        except IOError:
            logging.error("Fail to get attribute from %s", path)
            return ""

    def get_policy_attribute(self, attr) -> str:
        """
        Get the value of a specific attribute for the current CPU policy.

        Args:
            attr (str): The name of the attribute to query.

        Returns:
            str: The value of the specified attribute for the current policy.
        """
        return self.get_attribute(
            "cpufreq/policy{}/{}".format(self.policy, attr)
        )

    def set_attribute(self, attr, value) -> bool:
        """
        Set the value of a specific attribute in the CPU sysfs.

        Args:
            attr (str): The name of the attribute to set.
            value (str): The value to be set for the attribute.

        Returns:
            bool: True if the attribute is set successfully, False otherwise.
        """
        logging.debug("Setting value '%s' to attribute '%s'", value, attr)
        path = os.path.join(self.sys_cpu_dir, attr)
        try:
            with open(path, "w") as attr_file:
                attr_file.write(str(value))
        except PermissionError:
            logging.error("Permission denied when setting attribute %s", attr)
            return False
        except IOError:
            logging.error("Fail to set '%s' to attribute %s", value, path)
            return False
        return True

    def set_policy_attribute(self, attr, value) -> bool:
        """
        Set the value of a specific attribute for the current CPU policy.

        Args:
            attr (str): The name of the attribute to set.
            value (str): The value to be set for the attribute.

        Returns:
            bool: True if the attribute is set successfully, False otherwise.
        """
        return self.set_attribute(
            "cpufreq/policy{}/{}".format(self.policy, attr), value
        )

    def get_min_frequency(self) -> int:
        """
        Get the minimum CPU frequency for the current policy.

        Returns:
            int: The minimum CPU frequency in kHz.
        """
        frequency = self.get_policy_attribute("scaling_min_freq")
        return int(frequency) if frequency else 0

    def get_max_frequency(self) -> int:
        """
        Get the maximum CPU frequency for the current policy.

        Returns:
            int: The maximum CPU frequency in kHz.
        """
        frequency = self.get_policy_attribute("scaling_max_freq")
        return int(frequency) if frequency else 0

    def get_affected_cpus(self) -> List:
        """
        Get the list of affected CPUs for the current policy.

        Returns:
            List: A list of affected CPUs as strings.
        """
        values = self.get_policy_attribute("affected_cpus")
        return values.split()

    def get_supported_governors(self) -> List:
        """
        Get the list of supported governors for the current policy.

        Returns:
            List: A list of supported governors as strings.
        """
        values = self.get_policy_attribute("scaling_available_governors")
        return values.split()

    def get_governor(self) -> str:
        """
        Get the current governor for the current policy.

        Returns:
            str: The name of the current governor as a string.
        """
        return self.get_policy_attribute("scaling_governor")

    def set_governor(self, governor) -> bool:
        """
        Set the governor for the current policy.

        Args:
            governor (str): The name of the governor to set.

        Returns:
            bool: True if the governor is set successfully, False otherwise.
        """
        return self.set_policy_attribute("scaling_governor", governor)

    def set_frequency(self, frequency) -> bool:
        """
        Set the CPU frequency for the current policy.

        Args:
            frequency (int): The CPU frequency value to be set in kHz.

        Returns:
            bool: True if the frequency is set and verified successfully,
                  False otherwise.
        """
        logging.debug("Setting Frequency to %s", frequency)
        return self.set_policy_attribute("scaling_setspeed", frequency)


class CPUScalingTest:
    """A class for CPU scaling test operations."""

    def __init__(self, policy=0):
        """
        Initialize the CPUScalingTest object.

        Args:
            policy (int): The CPU policy number to be used (default is 0).
        """
        self.policy = policy
        self.info = CPUScalingInfo(policy=self.policy)

    def stress_cpus(self) -> subprocess.Popen:
        """
        Stress the CPU cores by running multiple dd processes.

        Returns:
            subprocess.Popen: A list of Popen objects representing the
                              dd processes spawned for each CPU core.
        """
        cpus_count = cpu_count()

        cmd = ["dd", "if=/dev/zero", "of=/dev/null"]
        processes = [subprocess.Popen(cmd) for _ in range(cpus_count)]
        return processes

    def stop_stress_cpus(self, processes):
        """
        Stop the CPU stress by terminating the specified dd processes.

        Args:
            processes (List[subprocess.Popen]): A list of Popen objects
                                                representing the dd processes.
        """
        for p in processes:
            p.terminate()
            p.wait()

    def print_policy_info(self):
        """
        Print information about the CPU frequency policy for the current CPU.
        """
        logging.info("## CPUfreq Policy%s Info ##", self.policy)
        logging.info("Affected CPUs:")
        if not self.info.governors:
            logging.info("    None")
        else:
            for cpu in self.info.affected_cpus:
                logging.info("    cpu%s", cpu)

        logging.info(
            "Supported CPU Frequencies: %s - %s MHz",
            self.info.min_freq / 1000,
            self.info.max_freq / 1000,
        )

        logging.info("Supported Governors:")
        if not self.info.governors:
            logging.info("    None")
        else:
            for governor in self.info.governors:
                logging.info("    %s", governor)

        logging.info("Current Governor: %s", self.info.original_governor)

    def test_driver_detect(self) -> bool:
        """
        Print the unique scaling drivers used by available CPU policies.

        If there are multiple drivers, they will be listed in a
        space-separated format. Example:
        "scaling_driver: driver_a driver_b"

        Returns:
            bool: True if the drivers are printed successfully,
                  False otherwise.
        """
        if not self.info.cpu_policies:
            return False
        drivers = []
        for policy in self.info.cpu_policies:
            driver = self.info.get_scaling_driver(policy)
            if driver not in drivers:
                drivers.append(driver)
        if not drivers:
            return False
        else:
            print("scaling_driver: {}".format(" ".join(drivers)))
            return True

    def test_userspace(self) -> bool:
        """
        Run the Userspace Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info("Running Userspace Governor Test")
        success = True
        governor = "userspace"
        if governor not in self.info.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        # Set freq to minimum, verify
        frequency = self.info.min_freq
        logging.info(
            "Setting CPU frequency to %u MHz", (int(frequency) / 1000)
        )
        if not self.info.set_frequency(frequency):
            success = False

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        if not curr_freq or (self.info.min_freq != curr_freq):
            logging.error(
                "Could not verify that cpu frequency is set to the minimum"
                " value of %s",
                self.info.min_freq,
            )
            success = False

        # Set freq to maximum, verify
        frequency = self.info.max_freq
        logging.info(
            "Setting CPU frequency to %u MHz", (int(frequency) / 1000)
        )
        if not self.info.set_frequency(frequency):
            success = False

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        if not curr_freq or (self.info.max_freq != curr_freq):
            logging.error(
                "Could not verify that cpu frequency is set to the minimum"
                " value of %s",
                self.info.max_freq,
            )
            success = False

        if success:
            logging.info("Userspace Governor Test: PASS")
        return success

    def test_performance(self) -> bool:
        """
        Run the Performance Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info("Running Performance Governor Test")
        success = True
        governor = "performance"
        if governor not in self.info.governors:
            logging.error("'%s' governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug(
            "Verifying current CPU frequency %s is close to max frequency",
            curr_freq,
        )
        if not curr_freq or (
            float(curr_freq) < 0.99 * float(self.info.max_freq)
        ):
            logging.error(
                "Current cpu frequency of %s is not close enough to the "
                "maximum value of %s",
                curr_freq,
                self.info.max_freq,
            )
            success = False

        if success:
            logging.info("Performance Governor Test: PASS")
        return success

    def test_powersave(self) -> bool:
        """
        Run the Powersave Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info("Running Powersave Governor Test")
        success = True
        governor = "powersave"
        if governor not in self.info.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug(
            "Verifying current CPU frequency %s is close to min frequency",
            curr_freq,
        )
        if not curr_freq or (
            float(curr_freq) * 0.99 > float(self.info.min_freq)
        ):
            logging.error(
                "Current cpu frequency of %s is not close enough to the "
                "minimum value of %s",
                curr_freq,
                self.info.min_freq,
            )
            success = False

        if success:
            logging.info("Powersave Governor Test: PASS")
        return success

    def test_ondemand(self) -> bool:
        """
        Run the Ondemand Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Ondemand Governor Test on CPU policy%s", self.policy
        )
        success = True
        governor = "ondemand"
        if governor not in self.info.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        logging.info("Stressing CPUs...")
        stress_process = self.stress_cpus()
        time.sleep(5)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.max_freq
            or not curr_freq
            or (self.info.max_freq != curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency is equal to the max frequency"
            )

        logging.info("Stop stressing CPUs...")
        self.stop_stress_cpus(stress_process)
        time.sleep(8)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.min_freq
            or not curr_freq
            or (self.info.max_freq <= curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has settled to a "
                "lower frequency"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency has settled to a "
                "lower frequency"
            )

        if success:
            logging.info("Ondemand Governor Test: PASS")
        return success

    def test_conservative(self) -> bool:
        """
        Run the Conservative Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Conservative Governor Test on CPU policy%s", self.policy
        )
        success = True
        governor = "conservative"
        if governor not in self.info.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        logging.info("Stressing CPUs...")
        stress_process = self.stress_cpus()
        time.sleep(5)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.max_freq
            or not curr_freq
            or (self.info.max_freq != curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency is equal to the max frequency"
            )

        logging.info("Stop stressing CPUs...")
        self.stop_stress_cpus(stress_process)
        time.sleep(8)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.min_freq
            or not curr_freq
            or (self.info.max_freq <= curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has settled to a "
                "lower frequency"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency has settled to a "
                "lower frequency"
            )

        if success:
            logging.info("Conservative Governor Test: PASS")
        return success

    def test_schedutil(self) -> bool:
        """
        Run the Schedutil Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Schedutil Governor Test on CPU policy%s", self.policy
        )
        success = True
        governor = "schedutil"
        if governor not in self.info.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.info.set_governor(governor):
            success = False

        logging.info("Stressing CPUs...")
        stress_process = self.stress_cpus()
        time.sleep(5)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.max_freq
            or not curr_freq
            or (self.info.max_freq != curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency is equal to the max frequency"
            )

        logging.info("Stop stressing CPUs...")
        self.stop_stress_cpus(stress_process)
        time.sleep(8)

        curr_freq = int(self.info.get_policy_attribute("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if (
            not self.info.min_freq
            or not curr_freq
            or (self.info.max_freq <= curr_freq)
        ):
            logging.error(
                "Could not verify that cpu frequency has settled to a "
                "lower frequency"
            )
            success = False
        else:
            logging.info(
                "Verified current CPU frequency has settled to a "
                "lower frequency"
            )

        if success:
            logging.info("Schedutil Governor Test: PASS")
        return success

    def restore_governor(self):
        """
        Restore the CPU governor to the original value.

        This method sets the CPU governor to the original governor value
        stored during initialization.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Restoring original governor to %s",
            self.info.original_governor
        )
        self.info.set_governor(self.info.original_governor)


def main():
    """
    Execute the CPU scaling test based on the provided command-line arguments.

    Command-line arguments:
        -d, --debug: Turn on debug level output for extra info during the
                     test run.
        --policy-resource: Print the policies list in Checkbox resource job
                           format.
        --driver-detect: Print the CPU scaling driver.
        --policy: Run the test on a specific CPU policy (default is policy 0).
        --governor: Run a specific governor test.

    Returns:
        int: The exit code of the test execution, 0 if successful, 1 otherwise.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )
    parser.add_argument(
        "--policy-resource",
        action="store_true",
        help="Print the polices list in Checkbox resource job format.",
    )
    parser.add_argument(
        "--driver-detect",
        action="store_true",
        help="Print the CPU scaling driver.",
    )
    parser.add_argument(
        "--policy",
        dest="policy",
        help="Run test on specific policy",
        default="0",
    )
    parser.add_argument(
        "--governor",
        dest="governor",
        help="Run Specific Governor Test",
    )
    args = parser.parse_args()

    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    info = CPUScalingInfo()
    if args.policy_resource:
        info.print_policies_list()
        return 0

    test = CPUScalingTest(policy=args.policy)
    if args.driver_detect:
        return 0 if test.test_driver_detect() else 1

    exit_code = 0
    try:
        test.print_policy_info()
        if not getattr(test, "test_{}".format(args.governor))():
            exit_code = 1
    except AttributeError:
        logging.exception("Given governor is not supported")
        return 1

    test.restore_governor()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
