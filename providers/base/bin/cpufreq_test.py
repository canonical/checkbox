#!/usr/bin/env python3

# Copyright (C) 2020 Canonical Ltd.
#
# Authors
#   Adrian Lane <adrian.lane@canonical.com>
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

"""Test and validate SUT CPU scaling capabilities via CPUFreq."""


from os import path
import multiprocessing
import collections
import threading
import argparse
import logging
import pprint
import random
import signal
import copy
import math
import time
import sys
import psutil


class CpuFreqTestError(Exception):
    """Exception handling."""
    def __init__(self, message):
        super().__init__()
        if 'scaling_driver' in message:
            logging.error(
                '%s\n## Fatal: scaling via cpufeq unsupported ##',
                message)
        # catch intel systems unable to change pstate driver mode
        elif 'intel_pstate/status' in message:
            pass
        else:
            logging.error(message)


class CpuFreqTest:
    """ Test cpufreq scaling capabilities."""
    # duration to stay at frequency (sec) (gt observe_interval)
    scale_duration = 15
    # frequency sampling interval (sec) (lt scale_duration)
    observe_interval = 1
    # max, min percentage of avg freq allowed to pass
    # values relative to target freq
    # ex: max = 110, min = 90 is 20% passing tolerance
    max_freq_pct = 110
    min_freq_pct = 90

    def __init__(self):
        """Instance attributes."""
        def append_max_min():
            """ Create scaling table from max_freq,
            min_freq cpufreq files.
            """
            scaling_freqs = []
            path_max = path.join('cpu0', 'cpufreq',
                                 'scaling_max_freq')
            path_min = path.join('cpu0', 'cpufreq',
                                 'scaling_min_freq')
            scaling_freqs.append(
                self._read_sysfs(path_max).rstrip('\n'))
            scaling_freqs.append(
                self._read_sysfs(path_min).rstrip('\n'))
            return scaling_freqs

        self.fail_count = 0
        self.path_root = '/sys/devices/system/cpu'
        self.__proc_list = []  # track spawned processes
        # Chainmap object for dict of dicts
        self.freq_chainmap = collections.ChainMap()
        # cpufreq driver
        path_scaling_driver = path.join('cpu0', 'cpufreq',
                                        'scaling_driver')
        self.scaling_driver = self._read_sysfs(
            path_scaling_driver).rstrip('\n')
        path_scaling_gvrnrs = path.join('cpu0', 'cpufreq',
                                        'scaling_available_governors')
        path_startup_governor = path.join('cpu0', 'cpufreq',
                                          'scaling_governor')
        self.scaling_gvrnrs = self._read_sysfs(
            path_scaling_gvrnrs).rstrip('\n').split()
        self.startup_governor = self._read_sysfs(
            path_startup_governor).rstrip('\n')

        # ensure the correct freq table is populated
        if 'acpi-cpufreq' in self.scaling_driver:
            path_scaling_freqs = path.join('cpu0', 'cpufreq',
                                           'scaling_available_frequencies')
            scaling_freqs = self._read_sysfs(
                path_scaling_freqs).rstrip('\n').split()
            self.scaling_freqs = list(
                map(int, scaling_freqs))
            # test freqs in ascending order
            self.scaling_freqs.sort()
        else:
            # setup path and status for intel pstate directives
            if 'intel_' in self.scaling_driver:
                # /sys/devices/system/cpu/intel_pstate/status
                self.path_ipst_status = path.join('intel_pstate', 'status')
                self.startup_ipst_status = self._read_sysfs(
                    self.path_ipst_status).rstrip('\n')
            # use max, min freq for scaling table
            self.scaling_freqs = list(
                map(int, append_max_min()))
            self.scaling_freqs.sort()
            self.startup_max_freq = self.scaling_freqs[1]
            self.startup_min_freq = self.scaling_freqs[0]

    def _read_sysfs(self, fpath):
        """Read sysfs/cpufreq file."""
        abs_path = path.join(self.path_root, fpath)
        try:
            with open(abs_path, 'r') as _file:
                data = _file.read()
        except OSError:
            raise CpuFreqTestError(
                'Unable to read file: %s' % abs_path)
        else:
            return data

    def _write_sysfs(self, fpath, data):
        """Write sysfs/cpufreq file, data type agnostic."""
        def return_bytes_utf(data):
            """Data type conversion to bytes utf."""
            try:
                data_enc = data.encode()
            except (AttributeError, TypeError):
                data_enc = str(data).encode()
            return bytes(data_enc)

        if not isinstance(data, bytes):
            data_utf = return_bytes_utf(data)
        else:
            # do not convert bytes()
            data_utf = data

        abs_path = path.join(self.path_root, fpath)
        try:
            with open(abs_path, 'wb') as _file:
                _file.write(data_utf)
        except OSError:
            raise CpuFreqTestError(
                'Unable to write file: %s' % abs_path)

    def _get_cores(self, fpath):
        """Get various core ranges, convert to list."""
        def list_core_rng(core_rng):
            """ Method to convert core range to list prior
            to iteration.
            """
            core_list = []
            # allow iteration over range: rng
            for core in core_rng.split(','):
                first_last = core.split('-')
                if len(first_last) == 2:
                    core_list += list(
                        range(int(first_last[0]),
                              int(first_last[1]) + 1))
                else:
                    core_list += [int(first_last[0])]
            return core_list

        core_rng = self._read_sysfs(fpath).strip('\n').strip()
        core_list = list_core_rng(core_rng)
        return core_list

    def _process_results(self):
        """Process results from CpuFreqCoreTest."""
        def comp_freq_dict(inner_key, inner_val):
            """Transpose and append results from subclass."""
            if inner_val:
                # get % avg_freq/target_freq
                result_pct = int((inner_val / inner_key) * 100)
                # append result %
                new_inner_val = [result_pct]
                if CpuFreqTest.min_freq_pct <= result_pct <= (
                        CpuFreqTest.max_freq_pct):
                    # append result pass/fail
                    new_inner_val.append('Pass')
                else:
                    new_inner_val.append('Fail')
                    # increment fail bit
                    self.fail_count += 1
            # append avg freq
            new_inner_val.append(int(inner_val))
            return new_inner_val

        # create master result table with dict comprehension
        freq_result_map = {
            outer_key: {
                inner_key: comp_freq_dict(inner_key, inner_val)
                for inner_key, inner_val in outer_val.items()
            }
            for outer_key, outer_val in self.freq_chainmap.items()
        }
        return freq_result_map

    def disable_thread_siblings(self):
        """Disable thread_siblings (aka hyperthreading)
        on all cores.
        """
        def get_thread_siblings():
            """Get hyperthread cores to offline."""
            thread_siblings = []
            online_cores = self._get_cores('online')
            for core in online_cores:
                fpath = path.join('cpu%i' % core,
                                  'topology', 'thread_siblings_list')
                # second core is sibling
                thread_siblings += self._get_cores(fpath)[1:]
            if thread_siblings:
                to_disable = set(thread_siblings) & set(online_cores)
                logging.info(
                    '* disabling thread siblings (hyperthreading):')
                logging.info(
                    '  - disabling cores: %s', to_disable)
            else:
                to_disable = False
            return to_disable

        to_disable = get_thread_siblings()
        if to_disable:
            for core in to_disable:
                fpath = path.join('cpu%i' % core, 'online')
                self._write_sysfs(fpath, 0)

    def set_governors(self, governor):
        """Set/change CpuFreq scaling governor; global on all cores."""
        logging.info('  - setting governor: %s', governor)
        online_cores = self._get_cores('online')
        for core in online_cores:
            fpath = path.join('cpu%i' % core,
                              'cpufreq', 'scaling_governor')
            self._write_sysfs(fpath, governor)

    def reset(self):
        """Enable all offline cpus,
        and reset max and min frequencies files.
        """
        def reset_intel_driver():
            """ Reset fn for pstate driver."""
            try:
                self._write_sysfs(
                    self.path_ipst_status, 'off')
            # if kernel/bios limitations present
            except CpuFreqTestError:
                # then reset via max, min freq files
                set_max_min()
                return
            logging.info('* resetting intel p_state cpufreq driver')
            # wait 300ms between setting driver modes
            time.sleep(.3)
            logging.info(
                '  - setting driver mode: %s', self.startup_ipst_status)
            self._write_sysfs(
                self.path_ipst_status, self.startup_ipst_status)

        def enable_off_cores():
            """Enable all present and offline cores."""
            present_cores = self._get_cores('present')
            try:
                offline_cores = self._get_cores('offline')
            # for -r (reset) arg invokation
            except ValueError:
                return

            to_enable = set(present_cores) & set(offline_cores)
            logging.info('* enabling thread siblings/hyperthreading:')
            logging.info('  - enabling cores: %s', to_enable)
            for core in to_enable:
                fpath = path.join('cpu%i' % core,
                                  'online')
                self._write_sysfs(fpath, 1)

        def set_max_min():
            """Set max_frequency and min_frequency cpufreq files."""
            logging.info('* restoring max, min freq files')
            present_cores = self._get_cores('present')
            for core in present_cores:
                path_max = path.join('cpu%i' % core,
                                     'cpufreq', 'scaling_max_freq')
                path_min = path.join('cpu%i' % core,
                                     'cpufreq', 'scaling_min_freq')
                # reset max freq
                self._write_sysfs(
                    path_max, self.startup_max_freq)
                # reset min freq
                self._write_sysfs(
                    path_min, self.startup_min_freq)

        logging.info('* restoring startup governor:')
        # in case test ends prematurely from prior run
        # and facilitate reset() called from args
        if 'userspace' in self.startup_governor:
            # may need to validate these assumptions
            self.startup_governor = 'ondemand'
        elif 'performance' in self.startup_governor:
            self.startup_governor = 'powersave'
        self.set_governors(self.startup_governor)

        # enable offline cores
        enable_off_cores()

        # reset sysfs for non-acpi_cpufreq systems
        if 'acpi-cpufreq' not in self.scaling_driver:
            if 'intel_' in self.scaling_driver:
                reset_intel_driver()
            else:
                set_max_min()

    def execute_test(self):
        """Execute cpufreq test, process results and return
        appropriate exit code.
        """
        def init_intel_driver():
            """Reset and set best available Intel driver mode.
            Some modes unavailable for certain processor:kernel/bios configs.
            """
            try:
                self._write_sysfs(
                    self.path_ipst_status, 'off')
            # for kernel/bios limitations
            except CpuFreqTestError:
                return

            logging.info(
                '* initializing intel_cpufreq driver:')
            # wait 300ms between changing driver modes
            time.sleep(.3)
            # prefer the intel_cpufreq driver (passive mode)
            self._write_sysfs(self.path_ipst_status, 'passive')
            cur_ipst_status = self._read_sysfs(
                self.path_ipst_status).rstrip('\n')
            logging.info('  - driver mode: %s', cur_ipst_status)

        logging.info('---------------------\n'
                     '| CpuFreqTest Begin |\n'
                     '---------------------')
        start_time = time.time()
        # disable hyperthreading
        self.disable_thread_siblings()

        # if intel, reset and set best compatible driver
        if 'intel_' in self.scaling_driver:
            init_intel_driver()

        logging.info('* configuring cpu governors:')
        # userspace governor required for scaling_setspeed
        if 'acpi-cpufreq' in self.scaling_driver:
            self.set_governors('userspace')
        else:
            self.set_governors('performance')

        # spawn core_tests concurrently
        logging.info('---------------------')
        self.spawn_core_test()
        # wrap up test
        logging.info('\n-----------------\n'
                     '| Test Complete |\n'
                     '-----------------\n')
        # reset state and cleanup
        logging.info('[Reset & Cleanup]')
        self.reset()

        # facilitate house cleaning
        if self.__proc_list:
            logging.info('* terminating dangling pids')
            for proc in self.__proc_list:
                # terminate dangling processes
                proc.terminate()
        # prove that we are single-threaded again
        logging.info('* active threads: %i\n', threading.active_count())

        # display results
        logging.warning('[CpuFreqTest Results]')  # for --quiet mode
        logging.info(
            ' - legend:\n'
            '   core: target_freq: [sampled_med_%, P/F, sampled_median],\n')
        # format result dict for human consumption
        logging.info(
            pprint.pformat(self._process_results()))
        # provide time under test for debug/verbose output
        end_time = time.time() - start_time
        logging.debug('[Test Took: %.3fs]', end_time)
        if self.fail_count:
            print('\n[Test Failed]\n'
                  '* core fail_count =', self.fail_count)
            return 1

        print('\n[Test Passed]')
        return 0

    def spawn_core_test(self):
        """Spawn concurrent scale testing on all online cores."""
        def run_worker_process(result_queue, affinity):
            """ Subclass instantiation & constructor for
            individual core.
            """
            worker = psutil.Process()
            # assign affinity, pin to core
            worker.cpu_affinity(affinity)
            # intantiate core_test
            cpu_freq_ctest = CpuFreqCoreTest(
                affinity[0], worker.pid)
            # execute freq scaling
            cpu_freq_ctest.scale_all_freq()
            # get results
            res_freq_map = cpu_freq_ctest.__call__()
            # place in result_queue
            result_queue.put(res_freq_map)

        def process_rqueue(queue_depth, result_queue):
            """Get and process core_test result_queue."""
            # get queued core_test results
            for _ in range(queue_depth):
                # pipe results from core_test
                worker_queue = result_queue.get()
                # append to chainmap object
                self.freq_chainmap = self.freq_chainmap.new_child(
                    worker_queue)
                # signal processing complete
                result_queue.task_done()
            logging.info('----------------------------')
            logging.info('* joining and closing queues')
            # nicely join and close queue
            try:
                result_queue.join()
            finally:
                result_queue.close()

        worker_list = []  # track spawned multiproc processes
        pid_list = []  # track spawned multiproc pids
        online_cores = self._get_cores('online')
        # delegate & spawn tests on other cores first
        # then run core 0 last (main() thread)
        online_cores.append(online_cores.pop(0))
        # create queue for piping results
        result_queue = multiprocessing.JoinableQueue()

        # assign affinity and spawn core_test
        for core in online_cores:
            affinity = [int(core)]
            affinity_dict = dict(affinity=affinity)
            worker = multiprocessing.Process(target=run_worker_process,
                                             args=(result_queue,),
                                             kwargs=affinity_dict)
            # start core_test
            worker.start()
            worker_list.append(worker)
            # track and log active child pids
            pid_list.append(worker.pid)

        # get, process queues
        process_rqueue(len(worker_list),
                       result_queue)

        # cleanup core_test pids
        logging.info('* joining worker processes:')
        for idx, worker in enumerate(worker_list):
            # join worker processes
            worker_return = worker.join()
            time.sleep(.1)
            if worker_return is None:
                logging.info(
                    '  - PID %s joined parent', pid_list[idx])
            else:
                # can cleanup in reset subroutine
                continue
        # update attribute for a 2nd pass terminate
        self.__proc_list = worker_list


class CpuFreqCoreTest(CpuFreqTest):
    """Subclass to facilitate concurrent frequency scaling."""
    class ObserveFreq:
        """Class for instantiating observation thread.
        Non-blocking and locked to system time to prevent
        linear timer drift as frequency scaling ramps up.
        """
        __slots__ = ('interval',
                     'callback',
                     'thread_timer',
                     'timer_running',
                     'next_call')

        def __init__(self, interval, callback):
            """Execute start_timer on class instantiation."""
            self.interval = interval
            self.callback = callback
            self.thread_timer = None
            self.timer_running = False
            self.next_call = time.time()
            # start event loop
            self.start_timer()

        def start_timer(self):
            """Facilitate callbacks at specified interval,
            accounts and corrects for drift.
            """
            if not self.timer_running:
                # offset interval
                self.next_call += self.interval
                # create time delta for consistent timing
                time_delta = self.next_call - time.time()
                # call self.observe() at end of time_delta
                self.thread_timer = threading.Timer(time_delta,
                                                    self.observe)
                # cleanup spawned timer threads on exit
                self.thread_timer.daemon = True
                self.thread_timer.start()
                self.timer_running = True

        def observe(self):
            """Trigger callback to sample frequency."""
            # reset timer_running
            self.timer_running = False
            # ObserveFreq not subclassed; callback to outer scope
            self.callback()
            # start another tt cycle
            self.start_timer()

        def stop(self):
            """Called when frequency scaling completed."""
            if self.thread_timer:
                # event loop end
                self.thread_timer.cancel()
            self.timer_running = False

    # as we may instantiate many instances
    __slots__ = ('core',
                 'pid',
                 '__instance_core',
                 '__instance_cpu',
                 '__instance_pid',
                 '__stop_scaling',
                 '__observed_freqs',
                 '__observed_freqs_dict',
                 '__read_sysfs',
                 '__write_sysfs')

    def __init__(self, core, pid):
        # perform base class inheritance
        super().__init__()
        # mangle instance attributes
        self.__instance_core = int(core)
        self.__instance_cpu = 'cpu%i' % core  # future call speedup
        self.__instance_pid = pid  # worker pid
        self.__stop_scaling = False  # signal.alarm semaphore
        self.__observed_freqs = []  # recorded freqs
        self.__observed_freqs_dict = {}  # core: recorded freqs
        # private _r/_w_sysfs methods for concurrent access w/o locks
        self.__read_sysfs = copy.deepcopy(self._read_sysfs)
        self.__write_sysfs = copy.deepcopy(self._write_sysfs)

    def __call__(self):
        """Have subclass return dict '{core: {trgt_f: med_f,}}'
        when called.
        """
        freq_map = {
            self.__instance_core: self.__observed_freqs_dict
        }
        return freq_map

    def _observe_freq_cb(self):
        """Callback method to sample frequency."""
        def get_cur_freq():
            """ Get current frequency.
            """
            fpath = path.join(self.__instance_cpu,
                              'cpufreq', 'scaling_cur_freq')
            freqs = self.__read_sysfs(fpath).rstrip('\n').split()[0]
            return int(freqs)

        self.__observed_freqs.append(get_cur_freq())
        # matrix mode
        logging.debug(self.__observed_freqs)

    def scale_all_freq(self):
        """Primary method to scale full range of freqs."""
        def calc_freq_median(obs_freqs):
            """ Calculate the median value of observed freqs.
            """
            n_samples = len(obs_freqs)
            # floor division req.
            c_index = n_samples // 2
            # odd number of samples in observed_freqs
            if n_samples % 2:
                freq_median = sorted(obs_freqs)[c_index]
            # even number of samples in observed_freqs
            else:
                freq_median = sum(
                    sorted(obs_freqs)[
                        (c_index - 1):(c_index + 1)
                    ]) / 2
            return freq_median

        def map_observed_freqs(target_freq):
            """Align freq key/values and split result lists
            for grouping.
            """
            # get median of observed freqs
            freq_median = calc_freq_median(self.__observed_freqs)
            # target_freq = key, freq_median = value
            self.__observed_freqs_dict.update(
                {target_freq: freq_median})

        def handle_alarm(*args):
            """Alarm trigger callback, unload core."""
            # *args for signal.signal() callback
            del args  # args unused
            # stop workload loop
            self.__stop_scaling = True

        def execute_workload(workload_n):
            """Perform maths to load core."""
            # compartmentalized for future development
            while not self.__stop_scaling:
                math.factorial(workload_n)

        def log_freq_scaling(freq, workload_n):
            """Provide feedback via logging."""
            logging.info('* testing: %s || target freq: %i ||'
                         ' work: fact(%i) || worker pid: %i',
                         self.__instance_cpu, freq,
                         workload_n, self.__instance_pid)

        def load_observe_map(freq):
            """Proxy fn to scale core to freq."""
            # gen randint for workload factorial calcs
            workload_n = random.randint(37512, 39845)
            # setup async alarm to kill load gen
            signal.signal(signal.SIGALRM, handle_alarm)
            # time to gen load
            signal.alarm(CpuFreqTest.scale_duration)
            # instantiate ObserveFreq and start data sampling
            observe_freq = self.ObserveFreq(
                interval=CpuFreqTest.observe_interval,
                callback=self._observe_freq_cb)
            # provide feedback on test status
            log_freq_scaling(freq, workload_n)
            # start loading core
            execute_workload(
                workload_n)
            # stop sampling
            observe_freq.stop()
            # map freq results to core
            map_observed_freqs(freq)

        # acpi supports full freq table scaling via scaling_setspeed
        if 'acpi-cpufreq' in self.scaling_driver:
            fpath = path.join(self.__instance_cpu,
                              'cpufreq', 'scaling_setspeed')
        # others support max, min freq scaling
        else:
            fpath = path.join(self.__instance_cpu,
                              'cpufreq', 'scaling_max_freq')

        # iterate over supported frequency scaling table
        for idx, freq in enumerate(self.scaling_freqs):
            # re-init some attributes after 1st pass
            if idx:
                # 200ms sync-up for aligning output
                time.sleep(.2)
                # reset freq list
                self.__observed_freqs = []
                # reset signal.signal() event loop bit
                self.__stop_scaling = False

            self.__write_sysfs(fpath, freq)
            # load core, observe freqs, map to obs_freq_dict
            load_observe_map(freq)


def parse_args_logging():
    """ Ingest arguments and init logging."""
    def init_logging(user_arg):
        """ Pass user arg and configure logging module."""
        # logging optimizations; per python logging lib docs
        logging._srcfile = None  # pylint: disable=protected-access
        # "%(processName)s prefix
        logging.logMultiprocessing = False
        # "%(process)d" prefix
        logging.logProcesses = False
        # "%(thread)d" & "%(threadName)s" prefixes
        logging.logThreads = False

        # log to stdout for argparsed logging lvls
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(user_arg.log_level)

        # log to stderr for exceptions
        stderr_formatter = logging.Formatter(
            '%(levelname)s: %(message)s')
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        stderr_handler.setFormatter(stderr_formatter)

        # setup base/root logger
        root_logger = logging.getLogger()
        # set root logging level
        root_logger.setLevel(logging.NOTSET)
        # add handlers for out, err
        root_logger.addHandler(stdout_handler)
        root_logger.addHandler(stderr_handler)

    parser = argparse.ArgumentParser()
    # only allow one arg to be passed
    parser_mutex_grp = parser.add_mutually_exclusive_group()
    parser_mutex_grp.add_argument(
        '-d', '--debug',
        dest='log_level',
        action='store_const',
        const=logging.DEBUG,
        # default logging level
        default=logging.INFO,
        help='debug/verbose output (stdout)')
    parser_mutex_grp.add_argument(
        '-q', '--quiet',
        dest='log_level',
        action='store_const',
        # repurpose logging level
        const=logging.WARNING,
        help='suppress output')
    parser_mutex_grp.add_argument(
        '-r', '--reset',
        action='store_true',
        help='reset cpufreq sysfs'
        ' (governor, ht, max/min, pstate)')
    user_arg = parser.parse_args()
    init_logging(user_arg)
    return user_arg


def main():
    # configure and start logging
    user_arg = parse_args_logging()
    # instantiate CpuFreqTest as cpu_freq_test
    cpu_freq_test = CpuFreqTest()
    # provide access to reset() method
    if user_arg.reset:
        print('[Reset CpuFreq Sysfs]')
        return cpu_freq_test.reset()
    return cpu_freq_test.execute_test()


if __name__ == '__main__':
    sys.exit(main())
