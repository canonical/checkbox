#!/usr/bin/env python3

# Copyright (C) 2020 Canonical Ltd.
#
# Authors
#   Rod Smith <rod.smith@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Run CPU, memory, and disk stress tests using the stress-ng binary program.
"""


from argparse import (
    ArgumentParser,
    RawTextHelpFormatter
)
from subprocess import (
    CalledProcessError,
    check_output,
    PIPE,
    Popen,
    run,
    STDOUT,
    TimeoutExpired
)
import os
import shlex
import shutil
import stat
import sys
import time
import uuid
import psutil
from checkbox_support.disk_support import Disk

# Swap filename
my_swap = None


class StressNg():
    """Interface with the external stress-ng binary."""
    # Accepts test parameters, runs the test, and enables access to test
    # results.

    def __init__(self,
                 stressors,
                 wrapper_timeout,
                 sng_timeout,
                 thread_count,
                 extra_options=""):

        self.stressors = stressors
        self.wrapper_timeout = wrapper_timeout
        self.sng_timeout = sng_timeout
        self.extra_options = extra_options
        self.thread_count = thread_count
        self.results = ""
        self.returncode = 0

    def run(self):
        """Run a stress-ng test, storing results in self.results."""

        stressor_list = "--" + " 0 --".join(self.stressors)
        # 0
        command = "stress-ng --aggressive --verify --timeout {} {} {} %i". \
            format(self.sng_timeout,
                   self.extra_options,
                   stressor_list,
                   self.thread_count)
        time_str = time.strftime("%d %b %H:%M", time.gmtime())
        if len(self.stressors) == 1:
            print("{}: Running stress-ng {} stressor for {:.0f} seconds...".
                  format(time_str, self.stressors[0], self.sng_timeout))
        else:
            print("{}: Running multiple stress-ng stressors in "
                  "parallel for {:.0f}".format(time_str, self.sng_timeout))
            print("seconds...")
        try:
            self.results = check_output(
                shlex.split(command), timeout=self.wrapper_timeout).decode(
                    encoding=sys.stdout.encoding)
        except CalledProcessError as err:
            print("** stress-ng exited with code {}".format(err.returncode))
            self.results = err.stdout.decode(encoding="utf-8")
            self.returncode = err.returncode
        except TimeoutExpired:
            print("** stress-ng timed out and was forcefully terminated")
            self.results = ""
            self.returncode = 1
        except KeyboardInterrupt:
            self.results = ""
            print("** stress-ng test was terminated by SIGINT (Ctrl+C)!")
            self.returncode = 1
        except FileNotFoundError:
            print("** stress-ng binary not found!")
            self.results = ""
            self.returncode = 1
        return self.returncode


# Define CPU-related functions...

def stress_cpu(args):
    """Run stress-ng tests on CPUs."""

    retval = 0
    stressors = ['af-alg', 'bsearch', 'context', 'cpu', 'crypt', 'hsearch',
                 'longjmp', 'lsearch', 'matrix', 'qsort', 'str', 'stream',
                 'tsearch', 'vecmath', 'wcs']
    # Add 10% to runtime; will forcefully terminate if stress-ng
    # fails to return in that time.
    end_time = 1.1 * args.base_time
    print("Estimated total run time is {:.0f} minutes\n".
          format(args.base_time / 60))

    test_object = StressNg(stressors=stressors,
                           sng_timeout=args.base_time,
                           wrapper_timeout=end_time,
                           extra_options="--metrics-brief --tz --times")
    retval = test_object.run()
    print(test_object.results)
    return retval


# Define memory-related functions...

def num_numa_nodes():
    """Return the number of NUMA nodes supported by the CPU."""

    try:
        return int(run(['numactl', '--hardware'],
                       stdout=PIPE).stdout.split()[1])
    except (ValueError, OSError, IndexError):
        return 1


def swap_space_ok(args):
    """Check available swap space."""
    # If swap space is too small, add more. The minimum
    # acceptable amount is defined as the GREATER of the amount specified
    # by the command-line -s/--swap-space option OR the amount specified
    # by the STRESS_NG_MIN_SWAP_SIZE environment variable. Both values are
    # specified in gibibytes (GiB). If neither is specified, a value of 0
    # (no swap required) is assumed.
    # Returns:
    # - True if OK (already or after adding more)
    # - False if insufficient swap space

    all_ok = True
    global my_swap
    min_swap_space = 0

    swap_size = max(os.environ.get('STRESS_NG_MIN_SWAP_SPACE', 0),
                    args.swap_size)
    print("Minimum swap space is set to {} GiB".format(swap_size))
    min_swap_space = swap_size * 1024 ** 3
    swap = psutil.swap_memory()
    if swap.total < min_swap_space:
        print("Swap space too small! Attempting to add more (this may take " +
              "a while)....")
        my_swap = "/swap-{}.img".format(uuid.uuid1())
        # Create swap file 10KiB bigger than minimum because there's a 4KiB
        # overhead in the file, so if it were exactly the minimum, it would
        # still be too small....
        try:
            with open(my_swap, "w+b") as f:
                # Swap file zeroed out and increased in size in 1KiB chunks to
                # avoid problems with sparse files and creating temporary RAM
                # use that potentially exceeds available RAM....
                for i in range(int((min_swap_space + 10240) / 1024)):
                    f.write(b"\x00" * 1024)
                f.flush()
        except OSError:
            print("Unable to create temporary swap file! Aborting test!")
            try:
                # In case the file was partially written but errored out
                # (say, because of a lack of disk space)
                os.remove(my_swap)
            except FileNotFoundError:
                # This exception will happen if the file doesn't exist at all
                pass
            all_ok = False
        if all_ok:
            os.chmod(my_swap, stat.S_IRUSR | stat.S_IWUSR)
            run(['mkswap', my_swap])
            run(['swapon', my_swap])
    swap = psutil.swap_memory()
    return swap.total >= min_swap_space


def stress_memory(args):
    """Run stress-ng tests on memory."""

    retval = 0
    if not swap_space_ok(args):
        print("** Swap space unavailable! Please activate swap space " +
              "and re-run this test!")
        return 1

    ram = psutil.virtual_memory()
    total_mem_in_gb = ram.total / (1024 ** 3)
    vrt = args.base_time + total_mem_in_gb * args.time_per_gig
    print("Total memory is {:.1f} GiB".format(total_mem_in_gb))
    print("Constant run time is {} seconds per stressor".format(
        args.base_time))
    print("Variable run time is {:.0f} seconds per stressor".format(vrt))
    print("Number of NUMA nodes is {}".format(num_numa_nodes()))

    # Constant-run-time stressors -- run them for the same length of time on
    # all systems....
    crt_stressors = ['bsearch', 'context', 'hsearch', 'lsearch', 'matrix',
                     'memcpy', 'null', 'pipe', 'qsort', 'stack', 'str',
                     'stream', 'tsearch', 'vm-rw', 'wcs', 'zero', 'mlock',
                     'mmapfork', 'mmapmany', 'mremap', 'shm-sysv',
                     'vm-splice']
    crt_stressors = crt_stressors[0:8]

    if num_numa_nodes() > 1:
        crt_stressors.append('numa')

    # Variable-run-time stressors -- run longer on systems with more RAM....
    vrt_stressors = ['malloc', 'mincore', 'vm', 'bigheap', 'brk', 'mmap']
    vrt_stressors = vrt_stressors[0:3]
    # stack, bigheap, brk
    ltc_stressors = ['stack', 'bigheap', 'brk']

    # add random selection of n stressors
    # and/or increase timeout(s)

    est_runtime = len(crt_stressors) * args.base_time + \
        len(vrt_stressors) * vrt
    print("Estimated total run time is {:.0f} minutes\n".
          format(est_runtime / 60))
    for stressor in crt_stressors:
        test_object = StressNg(stressors=stressor.split(),
                               sng_timeout=args.base_time,
                               wrapper_timeout=args.base_time * 2,
                               thread_count=0)
        retval = retval | test_object.run()
        print(test_object.results)
    for stressor in vrt_stressors:
        test_object = StressNg(stressors=stressor.split(),
                               sng_timeout=vrt,
                               wrapper_timeout=vrt * 2,
                               thread_count=0)
        retval = retval | test_object.run()
        print(test_object.results)
    for stressor in ltc_stressors:
        test_object = StressNg(stressors=stressor.split(),
                               sng_timeout=vrt,
                               wrapper_timeout=vrt * 2,
                               thread_count=8)
        retval = retval | test_object.run()
        print(test_object.results)
    if my_swap is not None and args.keep_swap is False:
        print("Deleting temporary swap file....")
        cmd = "swapoff {}".format(my_swap)
        Popen(shlex.split(cmd), stderr=STDOUT, stdout=PIPE).communicate()[0]
        os.remove(my_swap)
    return retval


def stress_disk(args):
    """Run stress-ng tests on disk."""

    disk_stressors = ['aio', 'aiol', 'chdir', 'chmod', 'chown', 'dentry',
                      'dir', 'fallocate', 'fiemap', 'filename', 'flock',
                      'fstat', 'hdd', 'ioprio', 'lease', 'locka', 'lockf',
                      'lockofd', 'madvise', 'mknod', 'msync', 'readahead',
                      'seal', 'seek', 'sync-file', 'xattr']

    retval = 0
    if "/dev" not in args.device and args.device != "":
        args.device = "/dev/" + args.device

    test_disk = Disk(args.device)
    if not test_disk.is_block_device():
        print("** {} is not a block device! Aborting!".format(args.device))
        return 1
    if test_disk.mount_filesystem(args.simulate):
        est_runtime = len(disk_stressors) * args.base_time
        print("Using test directory: '{}'".format(test_disk.test_dir))
        print("Estimated total run time is {:.0f} minutes\n".
              format(est_runtime / 60))
        retval = 0
        if not args.simulate:
            for stressor in disk_stressors:
                disk_options = "--temp-path {} ".format(test_disk.test_dir) + \
                    "--hdd-opts dsync --readahead-bytes 16M -k"
                test_object = StressNg(stressors=stressor.split(),
                                       sng_timeout=args.base_time,
                                       wrapper_timeout=args.base_time * 5,
                                       extra_options=disk_options)
                retval = retval | test_object.run()
                print(test_object.results)
        if test_disk.test_dir != "/tmp" and not args.simulate:
            shutil.rmtree(test_disk.test_dir, ignore_errors=True)
    else:
        print("** Unable to find a suitable partition! Aborting!")
        retval = 1

    return retval


# Main program body...

def main():
    """Run a stress_ng-based stress run."""

    parser = ArgumentParser(
        description="Run tests based on stress-ng",
        formatter_class=RawTextHelpFormatter)
    subparsers = parser.add_subparsers()

    # Main cli options
    cpu_parser = subparsers.add_parser('cpu', help=("Run CPU tests"))
    memory_parser = subparsers.add_parser('memory', help=("Run memory tests"))
    disk_parser = subparsers.add_parser('disk', help=("Run disk tests"))

    # CPU parameters
    cpu_parser.add_argument("-b", "--base-time", type=int, default=7200,
                            help="Run time, in seconds (default=7200)")

    # Memory parameters
    memory_parser.add_argument("-b", "--base-time", type=int,
                               help="Base time for each test, in seconds " +
                               "(default=300)", default=300)
    memory_parser.add_argument("-t", "--time-per-gig", type=int,
                               help="Extra time per GiB for some stressors," +
                               " in seconds (default=10)", default=10)
    memory_parser.add_argument("-s", "--swap-size", type=int,
                               help="swap size in GiB", default=0)
    memory_parser.add_argument("-k", "--keep-swap", action="store_true",
                               help="Keep swap file, if added by test")

    # Disk parameters
    disk_parser.add_argument("-d", "--device", type=str, required=True,
                             help="Disk device (/dev/sda, etc.)")
    disk_parser.add_argument("-b", "--base-time", type=int,
                             help="Time for each test, in seconds " +
                             "(default=240)", default=240)
    disk_parser.add_argument("-s", "--simulate", action="store_true",
                             help="Report disk info, but don't run tests")

    cpu_parser.set_defaults(func=stress_cpu)
    memory_parser.set_defaults(func=stress_memory)
    disk_parser.set_defaults(func=stress_disk)

    args = parser.parse_args()

    if shutil.which("stress-ng") is None:
        print("** The stress-ng utility is not installed; exiting!")
        return 1
    if not os.geteuid() == 0:
        print("** This program must be run as root (or via sudo); exiting!")
        return 1

    retval = args.func(args)
    print("retval is {}".format(retval))
    print("*" * 62)
    if retval == 0:
        print("* stress-ng test passed!")
    else:
        print("** stress-ng test failed!")
    print("*" * 62)

    return retval


sys.exit(main())
