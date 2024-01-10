#!/usr/bin/env python3
# Copyright Canonical 2023
# run_cyclictest.py
#
# Uses the cyclictest binary to run cyclictest and measure process latency.
# This test needs to run for at least 24 hours in order to provide useful data.
#
# The output from the test, as well as any errors, are then dumped into a file
# so the second part can check the results.  A passing test will depend on the
# maximum latency observed and whether that is an acceptable number.  This
# value depends on the DUT's platform and CPU.  These values are provided by
# Intel as part of the Real Time Key Performance Indicator (RT KPI) document.
#
# Pass conditions:
#   * Max latency is equal to or lower than the expected value for the DUT's HW
#   * 0 overflows (caused by a process waiting too long. also called a "miss")
#
# Fail conditions:
#   * Any errors from the test.
#   * Unacceptable values for Max Latency or Overflows.

import argparse
import subprocess


def run_it(duration):
    """
    This function runs the cyclictest command, and captures output

    Inputs:
    duration - the desired duration of the test in seconds.
    """

    # timeout must be larger than the test duration, otherwise the test will be
    # interrupted
    test_timeout = duration + 1

    cmd = ["chrt", "-f", "99", "cyclictest", "-a2-3", "-t2", "-m", "-p99",
           "-i250", "-h700", "-q", "-D", str(duration)]

    try:
        result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=test_timeout,
                check=True)
    except Exception as err:
        raise SystemExit(err)

    # Note: A returncode of 0 simply means the command executed successfully.
    # It does NOT mean the test passed (or failed.)
    # That will be determined by a separate function.
    return result


def lookup_max_latency():
    """
    The expected maximum latency is based on the HW platform and CPU.
    For instance, ADL-S with an i7-12700 has an expected maximum latency of
    11ms

    However, some hardware may not proper identification yet.
    In this case just return the largest latency listed in the document.
    """

    # In case we cannot determine the HW or the CPU of the DUT, use the largest
    # value from the table of expected maximum latency.
    MAX_ALLOWED_LATENCY = 100

    # TODO: Implement the methods to determine the platform and CPU, and use
    #       that to lookup the expected maximum latency.
    #
    #       For now, just return MAX_ALLOWED_LATENCY

    return MAX_ALLOWED_LATENCY


def verify_cyclictest_results(result):
    """
    This function takes output from the call to subprocess containing the
    output from a run of cyclictest and looks at std out to verify two things:
    1. The maximum latency from each thread did not exceed the maximum latency
       specified by Intel for the DUT's HW Platform and CPU.

    2. The number of overflows (scheduling misses) was 0 for each thread.

    Both conditions must be true for this function to return success (0)

    Sample output for these lines looks like:
    # Max Latencies: 00041 00046
    # Histogram Overflows: 00000 00000
    The values after these strings are the results from each thread.

    All other lines are ignored.
    """
    max_latency = lookup_max_latency()
    print("Maximum latency allowed: " + str(max_latency))
    # list of latencies, from each thread
    latencies = []

    # list of overflows (scheduling misses) from each thread
    overflows = []

    return_code = 0

    std_output = result.stdout.split("\n")
    for line in std_output:

        if "# Max Latencies" in line:
            latencies = line.split(":")[1].split()
            for latency in latencies:
                if int(latency) > max_latency:
                    print("Test fails.\tLatency : " + latency +
                          "\t-- Maximum Latency value of: " +
                          str(max_latency) + " exceeded.")
                    return_code = 1
                else:
                    print("Test passes.\tLatency : " + latency + " -- OK.")

        elif "# Histogram Overflows" in line:
            overflows = line.split(":")[1].split()
            for overflow in overflows:
                if int(overflow) > 0:
                    print("Test fails.\tOverflow: " + overflow +
                          " -- 0 Overflows expected.")
                    return_code = 1
                else:
                    print("Test passes.\tOverflow: " + overflow + " -- OK.")
            continue

    return return_code


def main():
    return_code = 0

    parser = argparse.ArgumentParser()
    # default duration is 86400 seconds = 24hr
    parser.add_argument("--duration", type=int, default=86400)
    args = parser.parse_args()

    result = run_it(args.duration)
    print("stdout: {}".format(result.stdout))
    print("stderr: {}\n".format(result.stderr))

    return_code = verify_cyclictest_results(result)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
