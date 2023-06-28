#!/usr/bin/env python3

import decimal
import os
import re
import sys
import time
import argparse
import logging

from typing import List
from subprocess import check_call, CalledProcessError


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


class CPUScalingTest:
    """A class for CPU scaling test operations."""
    def __init__(self):
        self.sys_cpu_directory = "/sys/devices/system/cpu"
        self.cpufreq_directory = os.path.join(
            self.sys_cpu_directory, "cpu0", "cpufreq"
        )
        self.min_freq = None
        self.max_freq = None
        self.cpufreq_directories = []
        self.governors = []
        self.original_governors = ""

    def get_cpu_freq_directories(self):
        """Get the path of cpufreq directories."""
        logging.debug("Getting CPU Frequency Directories")
        if not os.path.exists(self.sys_cpu_directory):
            logging.error("No file %s", self.sys_cpu_directory)
            return None

        # Look for cpu subdirectories
        pattern = re.compile("cpu(?P<cpuNumber>[0-9]+)")
        for subdirectory in os.listdir(self.sys_cpu_directory):
            match = pattern.search(subdirectory)
            if match and match.group("cpuNumber"):
                cpufreq_directory = os.path.join(
                    self.sys_cpu_directory, subdirectory, "cpufreq"
                )
                if not os.path.exists(cpufreq_directory):
                    logging.error(
                        "CPU %s has no cpufreq directory %s",
                        match.group("cpuNumber"),
                        cpufreq_directory,
                    )
                    return None
                self.cpufreq_directories.append(cpufreq_directory)

        if len(self.cpufreq_directories) == 0:
            return None

        logging.debug("Located the following CPU Freq Directories:")
        for line in self.cpufreq_directories:
            logging.debug("    %s", line)

        return self.cpufreq_directories

    def check_parameters(self, file) -> List[str]:
        """
        Check if parameter values from different directories are the same.

        Args:
            file (str): The name of the file to check parameters.

        Returns:
            List[str]: A list of parameter values if they are the same across
                       directories, or an empty list if the values are not the
                       same or an error occurs.
        """
        logging.debug("Checking Parameters for %s", file)
        current = []
        for directory in self.cpufreq_directories:
            parameters = self.get_parameter_values(directory, file)
            if not parameters:
                logging.error(
                    "Error: could not determine cpu parameters from %s",
                    os.path.join(directory, file),
                )
                return []
            if not current:
                current = parameters
            elif current != parameters:
                logging.warning(
                    "WARNING: values of %s in different cpufreq directories"
                    "are NOT the same",
                    file,
                )
                return []
        return current

    def get_parameter_values(self, cpufreq_directory, file) -> List[str]:
        """
        Get values of a parameter and return them as a list.

        Args:
            cpufreq_directory (str): The directory where the parameter file
                                     is located.
            file (str): The name of the parameter file.

        Returns:
            List[str]: A list of parameter values extracted from the file.

        Example:
            For example, if the file 'scaling_available_frequencies' contains:
            1200000 600000 300000

            The function will return:
            ["1200000", "600000", "300000"]
        """
        logging.debug("Getting Parameters %s from %s", file, cpufreq_directory)
        path = os.path.join(cpufreq_directory, file)
        with open(path, "r", encoding="utf-8") as parameter_file:
            for line in parameter_file:
                line = line.strip()
                if line:
                    return line.split()
        return []

    def set_parameter(
        self, set_file, read_file, value, automatch=False
    ) -> bool:
        """
        Set a value to the specified set_file and verify it in the read_file.

        Args:
            set_file (str): The name of the file to set the value.
            read_file (str): The name of the file to verify the value.
            value: The value to be set.
            automatch (bool, optional): If True, automatically search for the
                                        parameter files. Defaults to False.

        Returns:
            bool: True if the value was successfully set and verified,
                  False otherwise.
        """

        def find_parameter(target_file):
            logging.debug("Finding parameters for %s", target_file)
            for root, _, files in os.walk(self.sys_cpu_directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    if target_file in file_path:
                        return file_path
            return None

        logging.debug("Setting %s to %s", set_file, value)
        path = None
        if automatch:
            path = find_parameter(set_file)
        else:
            path = os.path.join(self.cpufreq_directory, set_file)

        try:
            check_call('echo "%s" > %s' % (value, path), shell=True)
        except CalledProcessError as exception:
            logging.exception("Command failed:")
            logging.exception(exception)
            return False

        # verify it has changed
        if automatch:
            path = find_parameter(read_file)
        else:
            path = os.path.join(self.cpufreq_directory, read_file)

        with open(path, "r", encoding="utf-8") as parameter_file:
            line = parameter_file.readline().strip()
            if not line or line != str(value):
                logging.error(
                    "Error: could not verify that %s was set to %s",
                    path,
                    value,
                )
                if line:
                    logging.error("Actual Value: %s", line)
                else:
                    logging.error("parameter file was empty")
                return False

        return True

    def set_frequency(self, frequency) -> bool:
        """
        Set the CPU frequency to the specified value.

        Args:
            frequency: The CPU frequency value to be set.

        Returns:
            bool: True if the frequency was successfully set and verified,
                  False otherwise.
        """
        logging.debug("Setting Frequency to %s", frequency)
        return self.set_parameter(
            "scaling_setspeed", "scaling_cur_freq", frequency
        )

    def set_governor(self, governor) -> bool:
        """
        Set a CPU governor to the system.

        Args:
            governor (str): The CPU governor value to be set.

        Returns:
            bool: True if the governor was successfully set and verified,
                  False otherwise.
        """
        logging.debug("Setting Governor to %s", governor)
        return self.set_parameter(
            "scaling_governor", "scaling_governor", governor
        )

    def get_parameter_value(self, parameter) -> str:
        """
        Get the value of the specified parameter from cpu0/cpufreq/.

        Args:
            parameter (str): The name of the parameter.

        Returns:
            str or None: The parameter value as a string, or None if
                         an error occurs.
        """
        logging.debug("Getting %s", parameter)
        param_file_path = os.path.join(self.cpufreq_directory, parameter)
        try:
            with open(param_file_path, "r", encoding="utf-8") as param_file:
                line = param_file.readline()
                if not line:
                    logging.error(
                        "Error: failed to get %s for %s",
                        parameter,
                        self.cpufreq_directory,
                    )
                    return None
                value = line.strip()
                return value
        except IOError as exception:
            logging.exception("Error: could not open %s", param_file_path)
            logging.exception(exception)

        return None

    def get_parameter_list(self, parameter) -> List[str]:
        """
        Get the same parameter value from multiple directories.

        Args:
            parameter (str): The name of the parameter to retrieve.

        Returns:
            List[str] or None: A list of resulting parameter values if
                               successful, or None if errors occur.
        """
        logging.debug("Getting parameter list")
        values = []
        for cpufreq_dir in self.cpufreq_directories:
            path = os.path.join(cpufreq_dir, parameter)
            try:
                with open(path, "r", encoding="utf-8") as param_file:
                    line = param_file.readline()
                    if not line:
                        logging.error(
                            "Error: failed to get %s for %s",
                            parameter,
                            cpufreq_dir,
                        )
                        return None
                    values.append(line.strip())
            except IOError as err:
                logging.error("Error reading file: %s", str(err))
                return None

        logging.debug("Found parameters:")
        for line in values:
            logging.debug("    %s", line)
        return values

    def simulate_pi(self):
        """
        Simulate the calculation of PI to make the CPU busy.

        This function performs a series of calculations to simulate the
        calculation of PI. It adjusts the precision, performs iterations,
        and updates the side length, height, and number of sides.

        Returns:
            bool: Always returns True.
        """
        decimal.getcontext().prec = 500
        side_length = decimal.Decimal(1)
        height = decimal.Decimal(3).sqrt() / 2
        num_sides = 6

        for _ in range(170):
            square_sum = (1 - height) ** 2 + side_length**2 / 4
            side_length = square_sum.sqrt()
            height = (1 - square_sum / 4).sqrt()
            num_sides = 2 * num_sides

        return True

    def get_supported_governors(self, resource_format=False) -> bool:
        """
        Get the list of supported CPU governors.

        Args:
            resource_format (bool, optional): If True, print the list of
                                              supported governors in a
                                              resource format. Defaults
                                              to False.

        Returns:
            bool: True if the list of supported governors is obtained
                  successfully, False otherwise.
        """
        all_governors = [
            "userspace",
            "performance",
            "powersave",
            "ondemand",
            "conservative",
            "schedutil",
        ]

        governor_filename = "scaling_available_governors"
        self.governors = self.check_parameters(governor_filename)
        if not self.governors:
            logging.error("No governor is supported")
            return False

        if resource_format:
            scaling_driver = self.get_parameter_value("scaling_driver")
            print("driver: {}".format(scaling_driver))
            for governor in all_governors:
                print(
                    "{}: {}".format(
                        governor,
                        "supported"
                        if governor in self.governors
                        else "unsupported",
                    )
                )
        return True

    def get_system_capabilities(self) -> bool:
        """
        Retrieve and log information about the system's
        CPU scaling capabilities.

        Returns:
            bool: True if the system capabilities were successfully retrieved
                  and logged, False otherwise.
        """
        logging.info("System Capabilites:")
        logging.info("-------------------------------------------------")
        if len(self.cpufreq_directories) > 1:
            logging.info("System has %u CPUs", len(self.cpufreq_directories))

        # Ensure all CPUs support the same frequencies
        freq_filename = "scaling_min_freq"
        self.min_freq = int(self.check_parameters(freq_filename)[0])
        if not self.min_freq:
            return False
        freq_filename = "scaling_max_freq"
        self.max_freq = int(self.check_parameters(freq_filename)[0])
        if not self.max_freq:
            return False
        logging.info(
            "Supported CPU Frequencies: %s - %s MHz",
            self.min_freq / 1000,
            self.max_freq / 1000,
        )
        # Check governors to verify all CPUs support the same control methods
        governor_filename = "scaling_available_governors"
        self.governors = self.check_parameters(governor_filename)
        if not self.governors:
            logging.error("No governor is supported")
            return False

        logging.info("Supported Governors: ")
        for governor in self.governors:
            logging.info("    %s", governor)

        self.original_governors = self.get_parameter_list("scaling_governor")
        if self.original_governors:
            logging.info("Current governors:")
            i = 0
            for gov in self.original_governors:
                logging.info("    cpu%u: %s", i, gov)
                i += 1
        else:
            logging.error(
                "Error: could not determine current governor settings"
            )
            return False

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
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        # Set freq to minimum, verify
        frequency = self.min_freq
        logging.info(
            "Setting CPU frequency to %u MHz", (int(frequency) / 1000)
        )
        if not self.set_frequency(frequency):
            success = False

        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        if not curr_freq or (self.min_freq != curr_freq):
            logging.error(
                "Could not verify that cpu frequency is set to the minimum"
                " value of %s",
                self.min_freq,
            )
            success = False

        # Set freq to maximum, verify
        frequency = self.max_freq
        logging.info(
            "Setting CPU frequency to %u MHz", (int(frequency) / 1000)
        )
        if not self.set_frequency(frequency):
            success = False

        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        if not curr_freq or (self.max_freq != curr_freq):
            logging.error(
                "Could not verify that cpu frequency is set to the minimum"
                " value of %s",
                self.max_freq,
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
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        logging.debug(
            "Verifying current frequency %s is close to max frequency",
            curr_freq,
        )
        if not curr_freq or (float(curr_freq) < 0.99 * float(self.max_freq)):
            logging.error(
                "Current cpu frequency of %s is not close enough to the "
                "maximum value of %s",
                curr_freq,
                self.max_freq,
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
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        logging.debug(
            "Verifying current frequency %s is close to min frequency",
            curr_freq,
        )
        if not curr_freq or (float(curr_freq) * 0.99 > float(self.min_freq)):
            logging.error(
                "Current cpu frequency of %s is not close enough to the "
                "minimum value of %s",
                curr_freq,
                self.min_freq,
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
        logging.info("Running Ondemand Governor Test")
        success = True
        governor = "ondemand"
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        if not self.verify_max_frequency():
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False

        if not self.verify_min_frequency():
            logging.error(
                "Could not verify that cpu frequency has settled to the "
                "minimum value"
            )
            success = False

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
        logging.info("Running Conservative Governor Test")
        success = True
        governor = "conservative"
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        if not self.verify_max_frequency():
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False

        # Set freq_step to 20% to increase the speed of frequency up and down
        path = os.path.join("conservative", "freq_step")
        if not self.set_parameter(path, path, 20, automatch=True):
            success = False
        if not self.verify_min_frequency():
            logging.error(
                "Could not verify that cpu frequency has settled to the "
                "minimum value"
            )
            success = False

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
        logging.info("Running Schedutil Governor Test")
        success = True
        governor = "schedutil"
        if governor not in self.governors:
            logging.error("%s governor not supported", governor)
            return False

        logging.info("Setting governor to %s", governor)
        if not self.set_governor(governor):
            success = False

        if not self.verify_max_frequency():
            logging.error(
                "Could not verify that cpu frequency has increased to the "
                "maximum value"
            )
            success = False

        if success:
            logging.info("Schedutil Governor Test: PASS")
        return success

    def verify_max_frequency(self) -> bool:
        """
        Verify if the CPU is running at the maximum frequency
        after performing calculations.

        Returns:
            bool: True if the CPU is running at the maximum frequency,
                  False otherwise.
        """
        logging.debug("Verifying maximum frequency")
        logging.info("Running PI calculation")
        # Do some calculation to make CPU busy
        self.simulate_pi()
        logging.info("Done.")
        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if not self.max_freq or not curr_freq or (self.max_freq != curr_freq):
            return False
        return True

    def verify_min_frequency(self, wait_time=8) -> bool:
        """
        Verify that the CPU is operating at the minimum frequency after
        sleeping for the specified wait_time in seconds.

        Args:
            wait_time (int, optional): The duration to sleep before checking
                                       the CPU frequency. Defaults to 8 secs.

        Returns:
            bool: True if the CPU is operating at the minimum frequency,
                  False otherwise.
        """
        logging.debug("Verifying minimum frequency")
        logging.info("Waiting %d seconds...", wait_time)
        time.sleep(wait_time)
        logging.info("Done.")
        curr_freq = int(self.get_parameter_value("scaling_cur_freq"))
        logging.debug("Current CPU frequency: %s MHz", (curr_freq / 1000))
        if not self.min_freq or not curr_freq or (self.min_freq != curr_freq):
            return False
        return True

    def restore_governors(self):
        """
        Restore the CPU governors to their original values.

        This method sets the CPU governor to the original governor value
        stored during initialization.
        """
        logging.info("-------------------------------------------------")
        logging.info(
            "Restoring original governor to %s", (self.original_governors[0])
        )
        self.set_governor(self.original_governors[0])


def main():
    """
    Run CPU Scaling Test.

    This function runs a CPU scaling test based on the provided command-line
    arguments.

    Command-line Arguments:
        -q, --quiet: Suppresses output.
        -c, --capabilities: Only outputs CPU capabilities.
        -d, --debug: Turns on debug level output for extra information
                     during the test run.
        --resource-format: Prints the capabilities in Checkbox resource job
                           format.
        --governor: Run a specific Governor test. Available options:
                    'userspace', 'performance', 'powersave', 'ondemand',
                    'conservative', 'schedutil'.

    Returns:
        int: The exit code of the test run. 0 if successful, 1 otherwise.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output."
    )
    parser.add_argument(
        "-c",
        "--capabilities",
        action="store_true",
        help="Only output CPU capabilities.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )
    parser.add_argument(
        "--resource-format",
        action="store_true",
        help="Print the capabilities in Checkbox resource job format.",
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

    if args.quiet or args.resource_format:
        # Not logging anything
        logger.setLevel(logging.CRITICAL + 1)

    test = CPUScalingTest()
    if not test.get_cpu_freq_directories():
        logging.info("CPU Frequency Scaling not supported")
        return 1

    if args.resource_format:
        logging.getLogger().setLevel(logging.ERROR)
        return 0 if test.get_supported_governors(resource_format=True) else 1

    if not test.get_system_capabilities():
        logging.error("Failed to get system capabilities")
        return 1

    exit_code = 0

    try:
        if not getattr(test, "test_{}".format(args.governor))():
            exit_code = 1
    except AttributeError:
        logging.error("Given governor is not supported")
        return 1

    test.restore_governors()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
