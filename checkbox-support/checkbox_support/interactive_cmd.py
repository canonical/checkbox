# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>
# This is a copy of the original module located here:
# https://github.com/kissiel/gallows
import re
import select
import subprocess
import sys
import time


class InteractiveCommand:
    def __init__(self, args):
        self._args = args
        self._is_running = False
        self._pending = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.kill()

    def start(self):
        self._proc = subprocess.Popen(
            self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        self._is_running = True
        self._poller = select.poll()
        self._poller.register(self._proc.stdout, select.POLLIN)

    def kill(self):
        if self._is_running:
            # explicitly closing files to make test not complain about leaking
            # them (GC race condition?)
            self._close_fds([self._proc.stdin, self._proc.stdout])
            self._proc.terminate()
            self._is_running = False
            self._proc.wait()

    def writeline(self, line, sleep=0.1):
        if not self._is_running:
            raise Exception('Process is not running')
        try:
            self._proc.stdin.write((line + '\n').encode(sys.stdin.encoding))
            self._proc.stdin.flush()
        except BrokenPipeError:
            self._close_fds([self._proc.stdin])
            raise
        time.sleep(sleep)

    def wait_for_output(self, timeout=5):
        events = self._poller.poll(timeout * 1000)
        if not events:
            self._pending = 0
            return None
        else:
            self._pending = len(self._proc.stdout.peek())
            return self._pending

    def wait_until_matched(self, pattern, timeout):
        assert timeout >= 0, "cannot wait until past times"
        deadline = time.time() + timeout
        output = ''
        while timeout > 0:
            self.wait_for_output(timeout)
            output += self.read_all()
            re_match = re.search(pattern, output)
            if re_match:
                return re_match
            timeout = deadline - time.time()
        return None

    def read_all(self):
        if not self._pending:
            return ''
        else:
            raw = self._proc.stdout.read(self._pending)
            self._pending = 0
            return raw.decode(sys.stdout.encoding)

    def write_repeated(self, command, pattern, attempts, timeout):
        """
        Write `command`, try matching `pattern` in the response and repeat
        for `attempts` times if pattern not matched.

        return True if it matched at any point. Or
        return False if attempts were depleted and pattern hasn't been matched
        """
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
