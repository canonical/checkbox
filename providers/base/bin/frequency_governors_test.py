#!/usr/bin/env python3

import decimal
import os
import re
import sys
import time
import argparse
import logging

from subprocess import check_output, check_call, CalledProcessError


class CPUScalingTest(object):

    def __init__(self):
        self.speedUpTolerance = 10.0  # percent
        self.retryLimit = 5
        self.retryTolerance = 5.0  # percent
        self.sysCPUDirectory = "/sys/devices/system/cpu"
        self.cpufreqDirectory = os.path.join(
            self.sysCPUDirectory, "cpu0", "cpufreq"
        )
        self.idaFlag = "ida"
        self.idaSpeedupFactor = 8.0  # percent
        self.selectorExe = "cpufreq-selector"
        self.ifSelectorExe = None
        self.minFreq = None
        self.maxFreq = None

    def getCPUFreqDirectories(self):
        logging.debug("Getting CPU Frequency Directories")
        if not os.path.exists(self.sysCPUDirectory):
            logging.error("No file %s" % self.sysCPUDirectory)
            return None
        # look for cpu subdirectories
        pattern = re.compile("cpu(?P<cpuNumber>[0-9]+)")
        self.cpufreqDirectories = list()
        for subdirectory in os.listdir(self.sysCPUDirectory):
            match = pattern.search(subdirectory)
            if match and match.group("cpuNumber"):
                cpufreqDirectory = os.path.join(
                    self.sysCPUDirectory, subdirectory, "cpufreq"
                )
                if not os.path.exists(cpufreqDirectory):
                    logging.error(
                        "CPU %s has no cpufreq directory %s"
                        % (match.group("cpuNumber"), cpufreqDirectory)
                    )
                    return None
                # otherwise
                self.cpufreqDirectories.append(cpufreqDirectory)
        if len(self.cpufreqDirectories) == 0:
            return None
        # otherwise
        logging.debug("Located the following CPU Freq Directories:")
        for line in self.cpufreqDirectories:
            logging.debug("    %s" % line)
        return self.cpufreqDirectories

    def checkParameters(self, file):
        logging.debug("Checking Parameters for %s" % file)
        current = None
        for cpufreqDirectory in self.cpufreqDirectories:
            parameters = self.getParameters(cpufreqDirectory, file)
            if not parameters:
                logging.error(
                    "Error: could not determine cpu parameters from %s"
                    % os.path.join(cpufreqDirectory, file)
                )
                return None
            if not current:
                current = parameters
            elif not current == parameters:
                return None
        return current

    def getParameters(self, cpufreqDirectory, file):
        logging.debug("Getting Parameters for %s" % file)
        path = os.path.join(cpufreqDirectory, file)
        file = open(path)
        while 1:
            line = file.readline()
            if not line:
                break
            if len(line.strip()) > 0:
                return line.strip().split()
        return None

    def setParameter(
        self, setFile, readFile, value, skip=False, automatch=False
    ):
        def findParameter(targetFile):
            logging.debug("Finding parameters for %s" % targetFile)
            for root, _, files in os.walk(self.sysCPUDirectory):
                for f in files:
                    rf = os.path.join(root, f)
                    if targetFile in rf:
                        return rf
            return None

        logging.debug("Setting %s to %s" % (setFile, value))
        path = None
        if not skip:
            if automatch:
                path = findParameter(setFile)
            else:
                path = os.path.join(self.cpufreqDirectory, setFile)

            try:
                check_call('echo "%s" > %s' % (value, path), shell=True)
            except CalledProcessError as exception:
                logging.exception("Command failed:")
                logging.exception(exception)
                return False

        # verify it has changed
        if automatch:
            path = findParameter(readFile)
        else:
            path = os.path.join(self.cpufreqDirectory, readFile)

        parameterFile = open(path)
        line = parameterFile.readline()
        if not line or line.strip() != str(value):
            logging.error(
                "Error: could not verify that %s was set to %s" % (path, value)
            )
            if line:
                logging.error("Actual Value: %s" % line)
            else:
                logging.error("parameter file was empty")
            return False

        return True

    def checkSelectorExecutable(self):
        logging.debug("Determining if %s is executable" % self.selectorExe)

        def is_exe(fpath):
            return os.path.exists(fpath) and os.access(fpath, os.X_OK)

        if self.ifSelectorExe is None:
            # cpufreq-selector default path
            exe = os.path.join("/usr/bin/", self.selectorExe)
            if is_exe(exe):
                self.ifSelectorExe = True
                return True
            for path in os.environ["PATH"].split(os.pathsep):
                exe = os.path.join(path, self.selectorExe)
                if is_exe(exe):
                    self.ifSelectorExe = True
                    return True

            self.ifSelectorExe = False
            return False

    def setParameterWithSelector(self, switch, setFile, readFile, value):
        logging.debug("Setting %s with %s to %s" % (setFile, switch, value))
        # Try the command for all CPUs
        skip = True
        if self.checkSelectorExecutable():
            try:
                check_call(
                    "cpufreq-selector -%s %s" % (switch, value), shell=True
                )
            except CalledProcessError as exception:
                logging.exception("Note: command failed: %s" % exception.cmd)
                skip = False
        else:
            skip = False

        return self.setParameter(setFile, readFile, value, skip)

    def setFrequency(self, frequency):
        logging.debug("Setting Frequency to %s" % frequency)
        return self.setParameterWithSelector(
            "f", "scaling_setspeed", "scaling_cur_freq", frequency
        )

    def setGovernor(self, governor):
        logging.debug("Setting Governor to %s" % governor)
        return self.setParameterWithSelector(
            "g", "scaling_governor", "scaling_governor", governor
        )

    def getParameter(self, parameter):
        value = None
        logging.debug("Getting %s" % parameter)
        parameterFilePath = os.path.join(self.cpufreqDirectory, parameter)
        try:
            parameterFile = open(parameterFilePath)
            line = parameterFile.readline()
            if not line:
                logging.error(
                    "Error: failed to get %s for %s"
                    % (parameter, self.cpufreqDirectory)
                )
                return None
            value = line.strip()
            return value
        except IOError as exception:
            logging.exception("Error: could not open %s" % parameterFilePath)
            logging.exception(exception)

        return None

    def getParameterList(self, parameter):
        logging.debug("Getting parameter list")
        values = list()
        for cpufreqDirectory in self.cpufreqDirectories:
            path = os.path.join(cpufreqDirectory, parameter)
            parameterFile = open(path)
            line = parameterFile.readline()
            if not line:
                logging.error(
                    "Error: failed to get %s for %s"
                    % (parameter, cpufreqDirectory)
                )
                return None
            values.append(line.strip())
        logging.debug("Found parameters:")
        for line in values:
            logging.debug("    %s" % line)
        return values

    def runLoadTest(self):
        logging.info("Running CPU load test...")
        try:
            output = check_output("taskset -pc 0 %s" % os.getpid(), shell=True)
            for line in output.decode().splitlines():
                logging.info(line)
        except CalledProcessError as exception:
            logging.exception("Could not set task affinity")
            logging.exception(exception)
            return None

        runTime = None
        tries = 0
        while tries < self.retryLimit:
            sys.stdout.flush()
            (
                start_utime,
                start_stime,
                start_cutime,
                start_cstime,
                start_elapsed_time,
            ) = os.times()
            self.pi()
            (
                stop_utime,
                stop_stime,
                stop_cutime,
                stop_cstime,
                stop_elapsed_time,
            ) = os.times()
            if not runTime:
                runTime = stop_elapsed_time - start_elapsed_time
            else:
                thisTime = stop_elapsed_time - start_elapsed_time
                if (
                    abs(thisTime - runTime) / runTime
                ) * 100 < self.retryTolerance:
                    return runTime
                else:
                    runTime = thisTime
            tries += 1

        logging.error(
            "Could not repeat load test times within %.1f%%"
            % self.retryTolerance
        )
        return None

    def pi(self):
        decimal.getcontext().prec = 500
        s = decimal.Decimal(1)
        h = decimal.Decimal(3).sqrt() / 2
        n = 6
        for i in range(170):
            s2 = (1 - h) ** 2 + s**2 / 4
            s = s2.sqrt()
            h = (1 - s2 / 4).sqrt()
            n = 2 * n

        return True

    def verifyMinimumFrequency(self, waitTime=5):
        logging.debug("Verifying minimum frequency")
        logging.info("Waiting %d seconds..." % waitTime)
        time.sleep(waitTime)
        logging.info("Done.")
        minimumFrequency = self.getParameter("scaling_min_freq")
        currentFrequency = self.getParameter("scaling_cur_freq")
        if (
            not minimumFrequency
            or not currentFrequency
            or (minimumFrequency != currentFrequency)
        ):
            return False

        # otherwise
        return True

    def getSystemCapabilities(self):
        logging.info("System Capabilites:")
        logging.info("-------------------------------------------------")

        # Do the CPUs support scaling?
        if not self.getCPUFreqDirectories():
            return False
        if len(self.cpufreqDirectories) > 1:
            logging.info("System has %u cpus" % len(self.cpufreqDirectories))

        # Ensure all CPUs support the same frequencies
        freqFileName = "scaling_min_freq"
        self.minFreq = int(self.checkParameters(freqFileName)[0])
        if not self.minFreq:
            return False
        freqFileName = "scaling_max_freq"
        self.maxFreq = int(self.checkParameters(freqFileName)[0])
        if not self.maxFreq:
            return False
        logging.info(
            "Supported CPU Frequencies: %s - %s MHz",
            self.minFreq / 1000,
            self.maxFreq / 1000,
        )
        # Check governors to verify all CPUs support the same control methods
        governorFileName = "scaling_available_governors"
        self.governors = self.checkParameters(governorFileName)
        if not self.governors:
            return False

        logging.info("Supported Governors: ")
        for governor in self.governors:
            logging.info("    %s" % governor)

        self.originalGovernors = self.getParameterList("scaling_governor")
        if self.originalGovernors:
            logging.info("Current governors:")
            i = 0
            for g in self.originalGovernors:
                logging.info("    cpu%u: %s" % (i, g))
                i += 1
        else:
            logging.error(
                "Error: could not determine current governor settings"
            )
            return False

        self.getCPUFlags()

        return True

    def getCPUFlags(self):
        logging.debug("Getting CPU flags")
        self.cpuFlags = None
        try:
            cpuinfo_file = open("/proc/cpuinfo", "r")
            cpuinfo = cpuinfo_file.read().split("\n")
            cpuinfo_file.close()

            for line in cpuinfo:
                if line.startswith("flags"):
                    pre, post = line.split(":")
                    self.cpuFlags = post.strip().split()
                    break
            logging.debug("Found the following CPU Flags:")
            for line in self.cpuFlags:
                logging.debug("    %s" % line)
        except OSError:
            logging.warning("Could not read CPU flags")

    def runUserSpaceTests(self):
        logging.info("Userspace Governor Test:")
        logging.info("-------------------------------------------------")
        self.minimumFrequencyTestTime = None
        self.maximumFrequencyTestTime = None

        success = True
        differenceSpeedUp = None
        governor = "userspace"
        if governor not in self.governors:
            logging.warning("Note: %s governor not supported" % governor)
        else:

            # Set the governor to "userspace" and verify
            logging.info("Setting governor to %s" % governor)
            if not self.setGovernor(governor):
                success = False

            # Set the CPU speed to its lowest value
            frequency = self.minFreq
            logging.info(
                "Setting CPU frequency to %u MHz" % (int(frequency) / 1000)
            )
            if not self.setFrequency(frequency):
                success = False

            # Verify the speed is set to the lowest value
            minimumFrequency = self.getParameter("scaling_min_freq")
            currentFrequency = self.getParameter("scaling_cur_freq")
            if (
                not minimumFrequency
                or not currentFrequency
                or (minimumFrequency != currentFrequency)
            ):
                logging.error(
                    "Could not verify that cpu frequency is set to the minimum"
                    " value of %s" % minimumFrequency
                )
                success = False

            # Run Load Test
            self.minimumFrequencyTestTime = self.runLoadTest()
            if not self.minimumFrequencyTestTime:
                logging.error(
                    "Could not retrieve the minimum frequency test's"
                    " execution time."
                )
                success = False
            else:
                logging.info(
                    "Minimum frequency load test time: %.2f"
                    % self.minimumFrequencyTestTime
                )

            # Set the CPU speed to it's highest value as above.
            frequency = self.maxFreq
            logging.info(
                "Setting CPU frequency to %u MHz" % (int(frequency) / 1000)
            )
            if not self.setFrequency(frequency):
                success = False

            maximumFrequency = self.getParameter("scaling_max_freq")
            currentFrequency = self.getParameter("scaling_cur_freq")
            if (
                not maximumFrequency
                or not currentFrequency
                or (maximumFrequency != currentFrequency)
            ):
                logging.error(
                    "Could not verify that cpu frequency is set to the"
                    " maximum value of %s" % maximumFrequency
                )
                success = False

            # Repeat workload test
            self.maximumFrequencyTestTime = self.runLoadTest()
            if not self.maximumFrequencyTestTime:
                logging.error(
                    "Could not retrieve the maximum frequency test's "
                    "execution time."
                )
                success = False
            else:
                logging.info(
                    "Maximum frequency load test time: %.2f"
                    % self.maximumFrequencyTestTime
                )

            # Verify MHz increase is comparable to time % decrease
            predictedSpeedup = float(maximumFrequency) / float(
                minimumFrequency
            )

            # If "ida" turbo thing, increase the expectation by 8%
            if self.cpuFlags and self.idaFlag in self.cpuFlags:
                logging.info(
                    "Found %s flag, increasing expected speedup by %.1f%%"
                    % (self.idaFlag, self.idaSpeedupFactor)
                )
                predictedSpeedup = predictedSpeedup * (
                    1.0 / (1.0 - (self.idaSpeedupFactor / 100.0))
                )

            if self.minimumFrequencyTestTime and self.maximumFrequencyTestTime:
                measuredSpeedup = (
                    self.minimumFrequencyTestTime
                    / self.maximumFrequencyTestTime
                )
                logging.info("CPU Frequency Speed Up: %.2f" % predictedSpeedup)
                logging.info("Measured Speed Up: %.2f" % measuredSpeedup)
                differenceSpeedUp = (
                    (measuredSpeedup - predictedSpeedup) / predictedSpeedup
                ) * 100
                logging.info(
                    "Percentage Difference %.1f%%" % differenceSpeedUp
                )
                if differenceSpeedUp > self.speedUpTolerance:
                    logging.error(
                        "Measured speedup vs expected speedup is %.1f%% "
                        "and is not within %.1f%% margin."
                        % (differenceSpeedUp, self.speedUpTolerance)
                    )
                    success = False
                elif differenceSpeedUp < 0:
                    logging.info(
                        "Measured speed up %.2f exceeded expected speedup %.2f"
                        % (measuredSpeedup, predictedSpeedup)
                    )
            else:
                logging.error(
                    "Not enough timing data to calculate speed differences."
                )

        return success

    def runOnDemandTests(self):
        logging.info("On Demand Governor Test:")
        logging.info("-------------------------------------------------")
        differenceOnDemandVsMaximum = None
        onDemandTestTime = None
        governor = "ondemand"
        success = True
        if governor not in self.governors:
            logging.warning("%s governor not supported" % governor)
        else:
            # Set the governor to "ondemand"
            logging.info("Setting governor to %s" % governor)
            if not self.setGovernor(governor):
                success = False

            # Wait a fixed period of time, then verify current speed
            # is the slowest in as before
            if not self.verifyMinimumFrequency():
                logging.error(
                    "Could not verify that cpu frequency has settled to the "
                    "minimum value"
                )
                success = False

            # Repeat workload test
            onDemandTestTime = self.runLoadTest()
            if not onDemandTestTime:
                logging.warning("No On Demand load test time available.")
                success = False
            else:
                logging.info(
                    "On Demand load test time: %.2f" % onDemandTestTime
                )

            if onDemandTestTime and self.maximumFrequencyTestTime:
                # Compare the timing to the max results from earlier,
                # again time should be within self.speedUpTolerance
                differenceOnDemandVsMaximum = (
                    abs(onDemandTestTime - self.maximumFrequencyTestTime)
                    / self.maximumFrequencyTestTime
                ) * 100
                logging.info(
                    "Percentage Difference vs. maximum frequency: %.1f%%"
                    % differenceOnDemandVsMaximum
                )
                if differenceOnDemandVsMaximum > self.speedUpTolerance:
                    logging.error(
                        "On demand performance vs maximum of %.1f%% is not "
                        "within %.1f%% margin"
                        % (differenceOnDemandVsMaximum, self.speedUpTolerance)
                    )
                    success = False
            else:
                logging.error(
                    "Not enough timing data to calculate speed differences."
                )

            # Verify the current speed has returned to the lowest speed again
            if not self.verifyMinimumFrequency():
                logging.error(
                    "Could not verify that cpu frequency has settled to the "
                    "minimum value"
                )
                success = False

        return success

    def runPerformanceTests(self):
        logging.info("Performance Governor Test:")
        logging.info("-------------------------------------------------")
        differencePerformanceVsMaximum = None
        governor = "performance"
        success = True
        if governor not in self.governors:
            logging.warning("%s governor not supported" % governor)
        else:
            # Set the governor to "performance"
            logging.info("Setting governor to %s" % governor)
            if not self.setGovernor(governor):
                success = False

            # let's run a warm-up task so the CPU can raise its freq
            performanceTestTime = self.runLoadTest()
            # Verify the current speed is close to scaling_max_freq
            maximumFrequency = self.getParameter("scaling_max_freq")
            currentFrequency = self.getParameter("scaling_cur_freq")
            if (
                not maximumFrequency
                or not currentFrequency
                or (float(currentFrequency) < 0.99 * float(maximumFrequency))
            ):
                logging.error(
                    "Current cpu frequency of %s is not close enough to the "
                    "maximum value of %s"
                    % (currentFrequency, maximumFrequency)
                )
                success = False

            # Repeat work load test
            performanceTestTime = self.runLoadTest()
            if not performanceTestTime:
                logging.error("No Performance load test time available.")
                success = False
            else:
                logging.info(
                    "Performance load test time: %.2f" % performanceTestTime
                )

            if performanceTestTime and self.maximumFrequencyTestTime:
                # Compare the timing to the max results
                differencePerformanceVsMaximum = (
                    abs(performanceTestTime - self.maximumFrequencyTestTime)
                    / self.maximumFrequencyTestTime
                ) * 100
                logging.info(
                    "Percentage Difference vs. maximum frequency: %.1f%%"
                    % differencePerformanceVsMaximum
                )
                if differencePerformanceVsMaximum > self.speedUpTolerance:
                    logging.error(
                        "Performance setting vs maximum of %.1f%% is not "
                        "within %.1f%% margin"
                        % (
                            differencePerformanceVsMaximum,
                            self.speedUpTolerance,
                        )
                    )
                    success = False
            else:
                logging.error(
                    "Not enough timing data to calculate speed differences."
                )

        return success

    def runConservativeTests(self):
        logging.info("Conservative Governor Test:")
        logging.info("-------------------------------------------------")
        differenceConservativeVsMinimum = None
        governor = "conservative"
        success = True
        if governor not in self.governors:
            logging.warning("%s governor not supported" % governor)
        else:
            # Set the governor to "conservative"
            logging.info("Setting governor to %s" % governor)
            if not self.setGovernor(governor):
                success = False

            # Set the frequency step to 20,
            # so that it jumps to minimum frequency
            path = os.path.join("conservative", "freq_step")
            if not self.setParameter(path, path, 20, automatch=True):
                success = False

            # Wait a fixed period of time,
            # then verify current speed is the slowest in as before
            if not self.verifyMinimumFrequency(10):
                logging.error(
                    "Could not verify that cpu frequency has settled "
                    "to the minimum value"
                )
                success = False

            # Set the frequency step to 0,
            # so that it doesn't gradually increase
            if not self.setParameter(path, path, 0, automatch=True):
                success = False

            # Repeat work load test
            conservativeTestTime = self.runLoadTest()
            if not conservativeTestTime:
                logging.error("No Conservative load test time available.")
                success = False
            else:
                logging.info(
                    "Conservative load test time: %.2f" % conservativeTestTime
                )

            if conservativeTestTime and self.minimumFrequencyTestTime:
                # Compare the timing to the max results
                differenceConservativeVsMinimum = (
                    abs(conservativeTestTime - self.minimumFrequencyTestTime)
                    / self.minimumFrequencyTestTime
                ) * 100
                logging.info(
                    "Percentage Difference vs. minimum frequency: %.1f%%"
                    % differenceConservativeVsMinimum
                )
                if differenceConservativeVsMinimum > self.speedUpTolerance:
                    logging.error(
                        "Performance setting vs minimum of %.1f%% is not "
                        "within %.1f%% margin"
                        % (
                            differenceConservativeVsMinimum,
                            self.speedUpTolerance,
                        )
                    )
                    success = False
            else:
                logging.error(
                    "Not enough timing data to calculate speed differences."
                )

        return success

    def restoreGovernors(self):
        logging.info(
            "Restoring original governor to %s" % (self.originalGovernors[0])
        )
        self.setGovernor(self.originalGovernors[0])


def main():
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
    args = parser.parse_args()

    # Set up the logging system (unless we don't want ANY logging)
    if not args.quiet or args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        format = "%(asctime)s %(levelname)-8s %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

    # If we DO want console output
    if not args.quiet:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(format, date_format))
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    # If we ALSO want to create a file for future reference
    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    test = CPUScalingTest()
    if not os.path.exists(test.cpufreqDirectory):
        logging.info("CPU Frequency Scaling not supported")
        return 0

    if not test.getSystemCapabilities():
        logging.error("Failed to get system capabilities")
        return 1

    returnValues = []
    if not args.capabilities:
        logging.info("Beginning Frequency Governors Testing")
        returnValues.append(test.runUserSpaceTests())
        returnValues.append(test.runOnDemandTests())
        returnValues.append(test.runPerformanceTests())
        returnValues.append(test.runConservativeTests())
        test.restoreGovernors()

    return 1 if False in returnValues else 0


if __name__ == "__main__":
    sys.exit(main())
