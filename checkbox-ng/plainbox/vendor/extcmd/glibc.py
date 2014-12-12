# encoding: UTF-8
# Copyright (c) 2010-2012 Linaro Limited
# Copyright (c) 2013 Canonical Ltd.
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.vendor.extcmd.glibc` - glibc-based extcmd
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

"""
import contextlib
import errno
import fcntl
import logging
import os
import signal
import sys

from plainbox.vendor.glibc import CLD_EXITED
from plainbox.vendor.glibc import CLD_KILLED
from plainbox.vendor.glibc import O_CLOEXEC
from plainbox.vendor.glibc import O_NONBLOCK
from plainbox.vendor.glibc import PIPE_BUF
from plainbox.vendor.glibc import SFD_CLOEXEC
from plainbox.vendor.glibc import SFD_NONBLOCK
from plainbox.vendor.glibc import dup3
from plainbox.vendor.pyglibc import pipe2
from plainbox.vendor.pyglibc import pthread_sigmask
from plainbox.vendor.pyglibc import signalfd
from plainbox.vendor.pyglibc.selectors import EVENT_READ
from plainbox.vendor.pyglibc.selectors import EpollSelector

from plainbox.vendor.extcmd import ExternalCommand
from plainbox.vendor.extcmd import SafeDelegate

_logger = logging.getLogger("plainbox.vendor.extcmd")
_bug_logger = logging.getLogger("plainbox.bug")


@contextlib.contextmanager
def close_fd(fd):
    """
    A context manager that ensures a file descriptor is closed in the end

    :param fd:
        The descriptor to close
    """
    try:
        yield fd
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise


_PLATFORM_DEFAULT_CLOSE_FDS = object()


class GlibcExternalCommandWithDelegate(ExternalCommand):
    """
    A non-portable implementation of ExternalCommandWithDelegate using certain
    glibc features. This version is *probably* unsafe to run from within a
    multi-threaded application.
    """

    def __init__(self, delegate, killsig=signal.SIGINT):
        self._delegate = SafeDelegate.wrap_if_needed(delegate)
        self._killsig = killsig

    def call(self, args, bufsize=-1, executable=None,
             stdin=None, stdout=None, stderr=None,
             preexec_fn=None, close_fds=_PLATFORM_DEFAULT_CLOSE_FDS,
             shell=False, cwd=None, env=None, universal_newlines=False,
             startupinfo=None, creationflags=0,
             restore_signals=True, start_new_session=False,
             pass_fds=()):
        # A few of the things are either not implemented or explicitly
        # unsupported, check for those and raise NotImplementedError or
        # ValueError respectively
        if universal_newlines is True:
            raise NotImplementedError(
                "universal_newlines=True is not implemented")
        if stdout is not None:
            raise ValueError("redirecting stdout is not supported")
        if stderr is not None:
            raise ValueError("redirecting stderr is not supported")
        if stdin is not None:
            raise ValueError("redirecting stdin is not supported")
        if close_fds is _PLATFORM_DEFAULT_CLOSE_FDS:
            close_fds = True
        selector = EpollSelector()
        signal_list = [signal.SIGCHLD, signal.SIGINT, signal.SIGQUIT]
        _logger.debug("Obtained: %r", selector)
        sfd = signalfd(signal_list, SFD_CLOEXEC | SFD_NONBLOCK)
        _logger.debug("Obtained: %r", sfd)
        sigmask = pthread_sigmask(signal_list)
        _logger.debug("Obtained: %r", sigmask)
        stdout_pair = pipe2(O_CLOEXEC)
        _logger.debug("Obtained: %r", stdout_pair)
        stderr_pair = pipe2(O_CLOEXEC)
        _logger.debug("Obtained: %r", stderr_pair)
        key = selector.register(stdout_pair[0], EVENT_READ, 'stdout')
        _logger.debug("Registered key with selector: %r", key)
        key = selector.register(stderr_pair[0], EVENT_READ, 'stderr')
        _logger.debug("Registered key with selector: %r", key)
        key = selector.register(sfd, EVENT_READ, 'sfd')
        _logger.debug("Registered key with selector: %r", key)
        with sigmask, sfd, selector, close_fd(stdout_pair[0]),\
                close_fd(stderr_pair[0]):
            # TODO: create fake args, kwargs
            self._delegate.on_begin(None, None)
            pid = os.fork()
            if pid == 0:
                # Close stdout and stderr, this will also flush the buffers
                sys.stdout.close()
                sys.stderr.close()
                # XXX: double check the order of actions below with
                # subprocess's internal counterpart.
                # Make stdout and stderr our pipe
                dup3(stdout_pair[1], 1, 0)
                dup3(stderr_pair[1], 2, 0)
                # Maybe close all open file descriptors
                if (close_fds or pass_fds):
                    pass_fds = frozenset(pass_fds)
                    max_fd = os.sysconf("SC_OPEN_MAX") or 256
                    for fd in range(3, max_fd):
                        # Except for those that are explicitly marked to keep
                        if fd not in pass_fds:
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                # Maybe modify the environment
                if env is not None:
                    os.environ.clear()
                    for env_k in env:
                        os.environ[env_k] = env[env_k]
                # Maybe change the current working directory
                if cwd is not None:
                    os.chdir(cwd)
                # Maybe restore the signal handlers
                if restore_signals:
                    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
                # Maybe start a new session
                if start_new_session:
                    os.setsid()
                # Maybe call the preexec function
                if preexec_fn is not None:
                    preexec_fn()
                # Execute the child process, maybe using a shell
                if shell:
                    os.execvp(executable or args[0], ['/bin/sh', '-c'] + args)
                else:
                    os.execvp(executable or args[0], args)
                # TODO: use a side channel to signal the failure, maybe?
                os.exit(-1)
            else:
                _logger.debug("Forked child process: %r", pid)
                # Make all pipes non-blocking as the loop below cannot work
                # with any blocking I/O.
                flags = fcntl.fcntl(stdout_pair[0], fcntl.F_GETFL)
                flags |= O_NONBLOCK
                fcntl.fcntl(stdout_pair[0], fcntl.F_SETFL, flags)
                flags = fcntl.fcntl(stderr_pair[0], fcntl.F_GETFL)
                flags |= O_NONBLOCK
                fcntl.fcntl(stderr_pair[0], fcntl.F_SETFL, O_NONBLOCK)
                # Close the write sides of the pipes
                os.close(stdout_pair[1])
                os.close(stderr_pair[1])
                return self._loop(selector, pid)

    def _handle_SIGCHLD(self, pid):
        _logger.debug("calling waitid() on process %d", pid)
        waitid_result = os.waitid(
            os.P_PID, pid, os.WNOHANG | os.WEXITED)
        _logger.debug("waitid() returned %r", waitid_result)
        if waitid_result is None:
            _logger.warning("waitid() returned nothing?")
            return
        if waitid_result.si_code == CLD_EXITED:
            returncode = waitid_result.si_status
            _logger.debug("Saw CLD_EXITED with return code: %r", returncode)
            self._delegate.on_end(returncode)
            return returncode
        elif waitid_result.si_code == CLD_KILLED:
            signal_num = waitid_result.si_status
            _logger.debug("Saw CLD_KILLED with signal: %r", signal_num)
            self._delegate.on_abnormal_end(signal_num)
            return -signal_num
        else:
            _bug_logger.error(
                "Unexpected si_code: %d", waitid_result.si_code)

    def _handle_SIGINT(self, pid):
        _logger.debug("Sending signal %d to process %d", self._killsig, pid)
        os.kill(pid, self._killsig)

    def _handle_SIGQUIT(self, pid):
        _logger.debug("Sending SIGQUIT to process %d", pid)
        os.kill(pid, signal.SIGQUIT)

    def _read_pipe(self, fd, name):
        assert name in ('stdout', 'stderr')
        data = os.read(fd, PIPE_BUF)
        _logger.debug("Read %d bytes of data from %s", len(data), name)
        if len(data) == 0:
            return True
        self._delegate.on_line(name, data)

    def _loop(self, selector, pid):
        waiting_for = set(['stdout', 'stderr', 'proc'])
        return_code = None
        while waiting_for:
            event_list = selector.select()
            for key, events in event_list:
                if key.data == 'sfd':
                    if events & EVENT_READ:
                        for fdsi in key.fileobj.read():
                            _logger.debug("read signal information: %r", fdsi)
                            if fdsi.ssi_signo == signal.SIGCHLD:
                                return_code = self._handle_SIGCHLD(pid)
                                if return_code is not None:
                                    # We're done, the child is gone, let's not
                                    # wait for anything anymore. This prevents
                                    # us from hanging on our pipes that may
                                    # still be alive forever.
                                    waiting_for.clear()
                            elif fdsi.ssi_signo == signal.SIGINT:
                                self._handle_SIGINT(pid)
                            elif fdsi.ssi_signo == signal.SIGQUIT:
                                self._handle_SIGQUIT(pid)
                            else:
                                _bug_logger.error(
                                    "read unexpected signal: %r", fdsi)
                    else:
                        _bug_logger.error(
                            "Unexpected event mask for signalfd: %d", events)
                else:
                    if events & EVENT_READ:
                        if self._read_pipe(key.fd, key.data):
                            _logger.debug(
                                "pipe %s depleted, unregistering and closing",
                                key.data)
                            selector.unregister(key.fd)
                            os.close(key.fd)
                            # NOTE: since we're cleaning waiting_for above,
                            # this part is optional
                            if key.data in waiting_for:
                                waiting_for.remove(key.data)
                    else:
                        _bug_logger.error(
                            "Unexpected event mask for pipe: %d", events)
        _logger.debug("Returning from extcmd: %d", return_code)
        return return_code
