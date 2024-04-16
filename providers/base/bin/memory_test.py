#!/usr/bin/env python3

import os
import sys
import re

from argparse import ArgumentParser
from subprocess import Popen, PIPE


class MemoryTest:

    def __init__(self):
        self.free_memory = 0
        self.system_memory = 0
        self.swap_memory = 0
        self.process_memory = 0
        self.is_process_limited = False

    @property
    def threaded_memtest_script(self):
        directory = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(directory, "threaded_memtest")

    def _get_memory(self):
        mem_info = open("/proc/meminfo", "r")
        try:
            while True:
                line = mem_info.readline()
                if line:
                    tokens = line.split()
                    if len(tokens) == 3:
                        if "MemTotal:" == tokens[0].strip():
                            self.system_memory = int(tokens[1].strip()) // 1024
                        elif tokens[0].strip() in [
                            "MemFree:",
                            "Cached:",
                            "Buffers:",
                        ]:
                            self.free_memory += int(tokens[1].strip()) // 1024
                        elif "SwapTotal:" == tokens[0].strip():
                            self.swap_memory = int(tokens[1].strip()) // 1024
                else:
                    break
        except Exception as e:
            print(
                "ERROR: Unable to get data from /proc/meminfo", file=sys.stderr
            )
            print(e, file=sys.stderr)
        finally:
            mem_info.close()

    def _command(self, command, shell=True):
        proc = Popen(command, shell=shell, stdout=PIPE, stderr=PIPE)
        return proc

    def _command_out(self, command, shell=True):
        proc = self._command(command, shell)
        return proc.communicate()[0].strip()

    def get_limits(self):
        self._get_memory()
        print("System Memory: %u MB" % self.system_memory)
        print("Free Memory: %u MB" % self.free_memory)
        print("Swap Memory: %u MB" % self.swap_memory)

        if self.system_memory == 0:
            print("ERROR: could not determine system RAM", file=sys.stderr)
            return False

        # Process Memory
        self.process_memory = self.free_memory
        try:
            arch = self._command_out("arch").decode()
            if (
                re.match(r"(i[0-9]86|s390|arm.*)", arch)
                and self.free_memory > 1024
            ):
                self.is_process_limited = True
                self.process_memory = 1024  # MB, due to 32-bit address space
                print(
                    "%s arch, Limiting Process Memory: %u"
                    % (arch, self.process_memory)
                )
        # others?  what about PAE kernel?
        except Exception as e:
            print(
                "ERROR: could not determine system architecture via arch",
                file=sys.stderr,
            )
            print(e, file=sys.stderr)
            return False
        return True

    def run(self):
        PASSED = 0
        FAILED = 1

        limits = self.get_limits()
        if not limits:
            return FAILED

        # if process memory is limited, run multiple processes
        if self.is_process_limited:
            print("Running Multiple Process Memory Test")
            if not self.run_multiple_process_test():
                return FAILED
        else:
            print("Running Single Process Memory Test")
            if not self.run_single_process_test():
                return FAILED

        # otherwised, passed
        return PASSED

    def run_single_process_test(self):
        if not self.run_threaded_memory_test():
            return False
        return True

    def run_multiple_process_test(self):
        processes = self.free_memory // self.process_memory
        # if not swap-less, add a process to hit swap
        if not self.swap_memory == 0:
            processes += 1
            # check to make sure there's enough swap
            required_memory = self.process_memory * processes
            if required_memory > self.system_memory + self.swap_memory:
                print(
                    "ERROR: this test requires a minimum of %u KB of swap "
                    "memory (%u configured)"
                    % (required_memory - self.system_memory, self.swap_memory),
                    file=sys.stderr,
                )
        print("Testing memory with %u processes" % processes)

        print("Running threaded memory test:")
        run_time = 60  # sec.
        if not self.run_processes(
            processes,
            "%s -qv -m%um -t%u"
            % (self.threaded_memtest_script, self.process_memory, run_time),
        ):
            print(
                "Multi-process, threaded memory Test FAILED", file=sys.stderr
            )
            return False

        return True

    def run_threaded_memory_test(self):
        # single-process threaded test
        print("Starting Threaded Memory Test")

        # run for Free Memory plus the lessor of 5% or 1GB
        memory = (self.free_memory * 5) / 100
        if memory > 1024:  # MB
            memory = 1024  # MB
        memory = memory + self.free_memory
        print("Running for %d MB total memory" % memory)

        # run a test that will swap
        if not self.swap_memory == 0:

            # is there enough swap memory for the test?
            if memory > self.system_memory + self.swap_memory:
                print(
                    "ERROR: this test requires a minimum of %u KB of swap "
                    "memory (%u configured)"
                    % (memory - self.system_memory, self.swap_memory),
                    file=sys.stderr,
                )
                return False

            # otherwise
            run_time = 60  # sec.
            print(
                "Running for more than free memory at %u MB for %u sec."
                % (memory, run_time)
            )

            command = "%s -qv -m%um -t%u" % (
                self.threaded_memtest_script,
                memory,
                run_time,
            )
            print("Command is: %s" % command)
            process = self._command(command)
            process.communicate()
            if process.returncode != 0:
                print(
                    "%s returned code %s"
                    % (self.threaded_memtest_script, process.returncode),
                    file=sys.stderr,
                )
                print("More Than Free Memory Test failed", file=sys.stderr)
                return False
            print("More than free memory test complete.")

        # run again for 15 minutes
        print("Running for free memory")
        process = self._command("%s -qv" % self.threaded_memtest_script)
        process.communicate()
        if process.returncode != 0:
            print("Free Memory Test failed", file=sys.stderr)
        else:
            print("Free Memory Test succeeded")
        sys.stdout.flush()
        return process.returncode == 0

    def run_processes(self, number, command):
        passed = True
        pipe = []
        for i in range(number):
            pipe.append(self._command(command))
            print("Started: process %u pid %u: %s" % (i, pipe[i].pid, command))
        sys.stdout.flush()
        waiting = True
        while waiting:
            waiting = False
            for i in range(number):
                if pipe[i]:
                    line = pipe[i].communicate()[0]
                    if line and len(line) > 1:
                        print("process %u pid %u: %s" % (i, pipe[i].pid, line))
                        sys.stdout.flush()
                    if pipe[i].poll() == -1:
                        waiting = True
                    else:
                        return_value = pipe[i].poll()
                        if return_value != 0:
                            print(
                                "ERROR: process  %u pid %u retuned %u"
                                % (i, pipe[i].pid, return_value),
                                file=sys.stderr,
                            )
                            passed = False
                        print(
                            "process %u pid %u returned success"
                            % (i, pipe[i].pid)
                        )
                        pipe[i] = None
        sys.stdout.flush()
        return passed


def main(args):
    parser = ArgumentParser()
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output."
    )
    args = parser.parse_args(args)

    if args.quiet:
        sys.stdout = open(os.devnull, "a")
        sys.stderr = open(os.devnull, "a")

    test = MemoryTest()
    return test.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
