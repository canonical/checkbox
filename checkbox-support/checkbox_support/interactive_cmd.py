# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>
# This is a copy of the original module located here:
# https://github.com/kissiel/gallows
import logging
import re
import select
import subprocess
import sys
import time


class InteractiveCommand:
    def __init__(self, args, log_level=logging.WARNING, log_name=None,
                 ignore_eperm=False, shell=True):
        self._args = args
        self._ignore_eperm = ignore_eperm
        self._shell = shell
        self._is_running = False
        self._pending = 0
        logger_name = log_name or self._args.split()[0]
        self._logger = logging.getLogger('iCMD:{}'.format(logger_name))
        self._logger.setLevel(log_level)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter(
            ("%(asctime)s - %(name)s - %(levelname)s -"
             " %(message)s"))
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.kill()
        except PermissionError:
            if not self._ignore_eperm:
                raise
            self._is_running = False

    def start(self):
        self._logger.info("Starting command. Args: %s" % self._args)
        self._proc = subprocess.Popen(
            self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=self._shell)
        self._is_running = True
        self._poller = select.poll()
        self._logger.debug("Registering poller")
        self._poller.register(self._proc.stdout, select.POLLIN)

    def kill(self):
        self._logger.info("Killing...")
        if self._is_running:
            # explicitly closing files to make test not complain about leaking
            # them (GC race condition?)
            self._logger.debug("Closing pipes...")
            self._close_fds([self._proc.stdin, self._proc.stdout])
            try:
                self._logger.debug("Check if process died after closing pipes")
                self._proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                self._logger.debug("wait() timed out.")
            self._logger.debug("Terminating...")
            self._proc.terminate()
            self._is_running = False
            self._logger.debug("Waiting for process to terminate...")
            self._proc.wait()
            self._logger.info("Killed.")

    def writeline(self, line, sleep=0.1):
        self._logger.info("Writing to process: %s" % line)
        if not self._is_running:
            self._logger.warning("Process is not running!")
            raise Exception('Process is not running')
        try:
            self._proc.stdin.write((line + '\n').encode(sys.stdin.encoding))
            self._logger.debug("Flushing...")
            self._proc.stdin.flush()
        except BrokenPipeError:
            self._logger.warning("Broken pipe when sending to the process!")
            self._close_fds([self._proc.stdin])
            raise
        time.sleep(sleep)

    def wait_for_output(self, timeout=5):
        self._logger.info("Waiting for output. Timeout: %s" % timeout)
        events = self._poller.poll(timeout * 1000)
        if not events:
            self._logger.debug("Process generated no output")
            self._pending = 0
            return None
        else:
            self._pending = len(self._proc.stdout.peek())
            self._logger.debug("Process generated %s" % self._pending)
            return self._pending

    def wait_until_matched(self, pattern, timeout):
        self._logger.info("Waiting until matched. Pattern: %s" % pattern)
        assert timeout >= 0, "cannot wait until past times"
        deadline = time.time() + timeout
        output = ''
        while timeout > 0:
            self.wait_for_output(timeout)
            output += self.read_all()
            re_match = re.search(pattern, output)
            if re_match:
                self._logger.debug("Pattern matched")
                return re_match
            self._logger.debug("Pattern not matched")
            timeout = deadline - time.time()
        self._logger.info("Timeout exhausted")
        return None

    def read_all(self):
        self._logger.info("Reading all")
        if not self._pending:
            self._logger.debug("Nothing to read")
            return ''
        else:
            raw = self._proc.stdout.read(self._pending)
            self._pending = 0
            decoded = raw.decode(sys.stdout.encoding)
            self._logger.debug("Read %s bytes. : %s" % (len(raw), decoded))
            return decoded

    def write_repeated(self, command, pattern, attempts, timeout):
        """
        Write `command`, try matching `pattern` in the response and repeat
        for `attempts` times if pattern not matched.

        return True if it matched at any point. Or
        return False if attempts were depleted and pattern hasn't been matched
        """
        self._logger.info("Write repeated called. Attempts: %s" % attempts)
        matched = None
        while not matched and attempts > 0:
            self.writeline(command)
            matched = self.wait_until_matched(pattern, timeout)
            if matched:
                break
            attempts -= 1
        return matched

    @property
    def is_running(self):
        return self._is_running

    def _close_fds(self, fds):
        for pipe in fds:
            try:
                pipe.close()
            except BrokenPipeError:
                pass
