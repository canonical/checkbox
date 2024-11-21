#!/usr/bin/env python3

import argparse
import contextlib
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


def with_timeout(timeout=10, interval=0.5):
    """
    Decorator to set a timeout for a function's execution.

    This decorator allows you to execute a function with a specified timeout
    duration. If the function does not return `True` within the given timeout,
    the wrapper function returns `False`. The wrapper function sleeps for a
    specified interval between each invocation until the timeout expires.

    Args:
      - timeout (float, optional): Maximum time duration (in seconds) to wait
        for the decorated function to return `True`. Defaults to 10 seconds.
      - interval (float, optional): Time interval (in seconds) between
        invocations within the timeout duration. Defaults to 0.5 seconds.

    Returns:
      - bool: Returns `True` if the decorated function returns `True` within
        the specified timeout; otherwise, returns `False`.
    """

    def decorator(func):
        def func_wrapper(*args, **kwargs):
            start_time = time.time()
            while time.time() - start_time < timeout:
                if func(*args, **kwargs):
                    return True
                time.sleep(interval)
            return False

        return func_wrapper

    return decorator


def probe_governor_module(expected_governor):
    """
    Attempt to probe and load a specific CPU frequency governor module.

    Args:
      - expected_governor (str): The name of the CPU frequency governor module
        to probe and load.

    Raises:
      - subprocess.CalledProcessError: If the 'modprobe' command encounters an
        error during the module loading process.
    """
    logging.warning(
        "Seems CPU frequency governors %s are not enable yet.",
        expected_governor,
    )
    module = "cpufreq_{}".format(expected_governor)
    logging.info("Attempting to probe %s ...", module)
    cmd = ["modprobe", module]
    try:
        subprocess.check_call(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
        logging.info("Probe module Successfully!")
    except subprocess.CalledProcessError as err:
        logging.error(err)
        logging.error("%s governor not supported", expected_governor)
        sys.exit(1)


def stress_cpus() -> List[subprocess.Popen]:
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


def stop_stress_cpus(processes):
    """
    Stop the CPU stress by terminating the specified dd processes.

    Args:
        processes (List[subprocess.Popen]): A list of Popen objects
                                            representing the dd processes.
    """
    for p in processes:
        p.terminate()
        p.wait()


@contextlib.contextmanager
def context_stress_cpus():
    """
    Context manager to stress CPU cores using multiple dd processes.
    """
    try:
        logging.info("Stressing CPUs...")
        processes = stress_cpus()
        yield
    finally:
        logging.info("Stop stressing CPUs...")
        stop_stress_cpus(processes)


class CPUScalingHandler:
    """A class for getting and setting CPU scaling information."""

    def __init__(self, policy=0):
        """
        Initialize the CPUScalingHandler object.

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

    def get_cpb(self, policy=0) -> str:
        """
        Get the core performance boost (cpb) used by a specific CPU policy.
        Ref. https://en.wikipedia.org/wiki/AMD_Turbo_Core

        Args:
            policy (int): The CPU policy number to query (default is 0).

        Returns:
            str: The value of the cpb for the specified policy.
                 1 means enabled, 0 means disabled.
        """
        path = os.path.join(
            self.sys_cpu_dir,
            "cpufreq",
            "policy{}".format(policy),
            "cpb",
        )
        try:
            with open(path, "r") as attr_file:
                line = attr_file.read()
                return line.strip()
        except IOError:
            print("ERROR: Fail to get cpb from {}".format(path))
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
            print("policy: {}".format(policy))
            print("scaling_driver: {}".format(self.get_scaling_driver(policy)))
            print("cpb: {}".format(self.get_cpb(policy)))
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

    def get_current_frequency(self) -> int:
        """
        Get the current CPU frequency for the current policy.

        Returns:
            int: The current CPU frequency in kHz.
        """
        frequency = self.get_policy_attribute("scaling_cur_freq")
        logging.debug("Current CPU frequency: %s", frequency)
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

    @contextlib.contextmanager
    def context_set_governor(self, governor):
        """
        Context manager to temporarily set a CPU frequency governor and
        then restores the original governor.

        Args:
        - governor (str): The CPU frequency governor to set within the context.

        Raises:
        - SystemExit: If setting the governor fails during setup or teardown.
        """
        try:
            if not self.set_policy_attribute("scaling_governor", governor):
                sys.exit(1)
            yield
        finally:
            logging.debug("-----------------TEARDOWN-----------------")
            logging.debug(
                "Restoring original governor to %s",
                self.original_governor,
            )
            if not self.set_policy_attribute(
                "scaling_governor", self.original_governor
            ):
                sys.exit(1)

    @contextlib.contextmanager
    def context_set_frequency(self, frequency):
        """
        Context manager to temporarily set a CPU frequency and
        then restores the orignal frequency.

        Args:
        - frequency (str or int): The CPU frequency to set within the context.

        Raises:
        - SystemExit: If setting the frequency fails during setup or teardown.

        """
        try:
            original_frequency = self.get_current_frequency()
            if not self.set_frequency(frequency):
                sys.exit(1)
            yield
        finally:
            logging.debug("-----------------TEARDOWN-----------------")
            logging.debug(
                "Restoring original frequency to %s",
                original_frequency,
            )
            if not self.set_frequency(original_frequency):
                sys.exit(1)

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
        self.handler = CPUScalingHandler(policy=self.policy)

    def print_policy_info(self):
        """
        Print information about the CPU frequency policy for the current CPU.
        """
        logging.info("## CPUfreq Policy%s Info ##", self.policy)
        logging.info("Affected CPUs:")
        if not self.handler.governors:
            logging.info("    None")
        else:
            for cpu in self.handler.affected_cpus:
                logging.info("    cpu%s", cpu)

        logging.info(
            "Supported CPU Frequencies: %s - %s MHz",
            self.handler.min_freq / 1000,
            self.handler.max_freq / 1000,
        )

        logging.info("Supported Governors:")
        if not self.handler.governors:
            logging.info("    None")
        else:
            for governor in self.handler.governors:
                logging.info("    %s", governor)

        logging.info("Current Governor: %s", self.handler.original_governor)

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
        if not self.handler.cpu_policies:
            return False
        drivers = []
        for policy in self.handler.cpu_policies:
            driver = self.handler.get_scaling_driver(policy)
            if driver and driver not in drivers:
                drivers.append(driver)
        if not drivers:
            return False
        else:
            print("scaling_driver: {}".format(" ".join(drivers)))
            return True

    @with_timeout()
    def is_frequency_equal_to_target(self, target) -> bool:
        """
        Check if the current CPU frequency matches the target frequency.

        Args:
        - target (str or int): The target CPU frequency to compare against.

        Returns:
        - bool: Returns True if the current frequency matches the target
                frequency; otherwise, returns False.
        """
        curr_freq = self.handler.get_current_frequency()
        return curr_freq == target

    @with_timeout()
    def is_frequency_settled_down(self) -> bool:
        """
        Check if the current CPU frequency has settled down below the maximum.

        Returns:
        - bool: Returns True if the current frequency is below the maximum;
                otherwise, returns False.
        """
        curr_freq = self.handler.get_current_frequency()
        return curr_freq < self.handler.max_freq

    def test_frequency_influence(self, governor, target_freq=None) -> bool:
        """
        Test the influence of CPU frequency based on the provided governor.

        This function tests the influence of CPU frequency settings by
        setting different governors and verifying if the CPU frequency
        behaves as expected.

        Args:
        - governor (str): The CPU frequency governor to test.
        - target_freq (int, optional): The target CPU frequency for the
                                       'userspace' governor. Defaults to None.

        Returns:
        - bool: Returns True if all verification checks pass;
                otherwise, returns False.

        Raises:
        - SystemExit: If an unsupported governor is provided.
        """
        frequencies_mapping = {
            "performance": (self.handler.max_freq, "Max."),
            "powersave": (self.handler.min_freq, "Min."),
            "ondemand": (self.handler.max_freq, "Max."),
            "conservative": (self.handler.max_freq, "Max."),
            "schedutil": (self.handler.max_freq, "Max."),
        }
        success = True
        with self.handler.context_set_governor(governor):
            if governor in ["ondemand", "conservative", "schedutil"]:
                with context_stress_cpus():
                    if self.is_frequency_equal_to_target(
                        target=frequencies_mapping[governor][0]
                    ):
                        logging.info(
                            "Verified current CPU frequency is equal to "
                            "%s frequency %s MHz",
                            frequencies_mapping[governor][1],
                            (frequencies_mapping[governor][0] / 1000),
                        )
                    else:
                        success = False
                        logging.error(
                            "Could not verify that cpu frequency is equal to "
                            "%s frequency %s MHz",
                            frequencies_mapping[governor][1],
                            (frequencies_mapping[governor][0] / 1000),
                        )
                if self.is_frequency_settled_down():
                    logging.info(
                        "Verified current CPU frequency has settled to a "
                        "lower frequency"
                    )
                else:
                    success = False
                    logging.error(
                        "Could not verify that cpu frequency has settled to a "
                        "lower frequency"
                    )
            elif governor == "userspace":
                with self.handler.context_set_frequency(target_freq):
                    if self.is_frequency_equal_to_target(
                        target=target_freq,
                    ):
                        logging.info(
                            "Verified current CPU frequency is equal to "
                            "frequency %s MHz",
                            (target_freq / 1000),
                        )
                    else:
                        success = False
                        logging.error(
                            "Could not verify that cpu frequency is equal to "
                            "frequency %s MHz",
                            (target_freq / 1000),
                        )
            elif governor in ["performance", "powersave"]:
                if self.is_frequency_equal_to_target(
                    target=frequencies_mapping[governor][0],
                ):
                    logging.info(
                        "Verified current CPU frequency is close to "
                        "%s frequency %s MHz",
                        frequencies_mapping[governor][1],
                        (frequencies_mapping[governor][0] / 1000),
                    )
                else:
                    success = False
                    logging.error(
                        "Could not verify that cpu frequency has close to "
                        "%s frequency %s MHz",
                        frequencies_mapping[governor][1],
                        (frequencies_mapping[governor][0] / 1000),
                    )
            else:
                sys.exit("Governor '{}' not supported".format(governor))
        return success

    def test_userspace(self) -> bool:
        """
        Run the Userspace Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Userspace Governor Test on CPU policy%s", self.policy
        )
        governor = "userspace"
        return self.test_frequency_influence(
            governor,
            self.handler.max_freq,
        ) and self.test_frequency_influence(
            governor,
            self.handler.min_freq,
        )

    def test_performance(self) -> bool:
        """
        Run the Performance Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Performance Governor Test on CPU policy%s", self.policy
        )
        governor = "performance"
        return self.test_frequency_influence(governor)

    def test_powersave(self) -> bool:
        """
        Run the Powersave Governor Test.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Running Powersave Governor Test on CPU policy%s", self.policy
        )
        governor = "powersave"
        return self.test_frequency_influence(governor)

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
        governor = "ondemand"
        return self.test_frequency_influence(governor)

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
        governor = "conservative"
        return self.test_frequency_influence(governor)

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
        governor = "schedutil"
        return self.test_frequency_influence(governor)


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
        default=0,
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

    handler = CPUScalingHandler()
    if args.policy_resource:
        handler.print_policies_list()
        sys.exit(0)

    test = CPUScalingTest(policy=args.policy)
    if args.driver_detect:
        sys.exit(0) if test.test_driver_detect() else sys.exit(1)

    try:
        test.print_policy_info()
        if args.governor not in handler.governors:
            probe_governor_module(args.governor)
        if not getattr(test, "test_{}".format(args.governor))():
            sys.exit(1)
    except AttributeError:
        logging.error("Given governor is not supported")
        sys.exit(1)


if __name__ == "__main__":
    main()
