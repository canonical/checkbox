# Copyright (c) 2010-2012 Linaro Limited
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
A convenience wrapper around subprocess.Popen that allows the caller to
easily observe all stdout/stderr activity in real time.
"""

__version__ = (1, 0, 0, "beta", 4)

from queue import Queue
import abc
import signal
import subprocess
import sys
import threading
try:
    import posix
except ImportError:
    posix = None


class ExternalCommand(object):
    """
    A subprocess.Popen wrapper with that is friendly for sub-classing with
    common .call() and check_call() methods.
    """

    def call(self, *args, **kwargs):
        """
        Invoke a sub-command and wait for it to finish.

        Returns the command error code
        """
        proc = self._popen(*args, **kwargs)
        proc.wait()
        return proc.returncode

    def check_call(self, *args, **kwargs):
        """
        Invoke a sub-command and wait for it to finish while raising exception
        if the return code is not zero.

        The raised exception is the same as raised by subprocess.check_call(),
        that is :class:`subprocess.CalledProcessError`
        """
        returncode = self.call(*args, **kwargs)
        if returncode != 0:
            raise subprocess.CalledProcessError(
                returncode, kwargs.get("args") or args[0])
        return returncode

    def _popen(self, *args, **kwargs):
        if posix:
            kwargs['close_fds'] = True
        return subprocess.Popen(*args, **kwargs)


class IDelegate(object, metaclass=abc.ABCMeta):
    """
    Interface class for delegates compatible with ExtrnalCommandWithDelegate
    """

    @abc.abstractmethod
    def on_begin(self, args, kwargs):
        """
        Callback invoked when a command begins
        """

    @abc.abstractmethod
    def on_line(self, stream_name, line):
        """
        Callback invoked for each line of the output
        """

    @abc.abstractmethod
    def on_end(self, returncode):
        """
        Callback invoked when a command ends
        """

    @abc.abstractmethod
    def on_interrupt(self):
        """
        Callback invoked when the user triggers KeyboardInterrupt
        """


class DelegateBase(IDelegate):
    """
    An IDelegate implementation that does nothing
    """

    def on_begin(self, args, kwargs):
        """
        Do nothing
        """

    def on_line(self, stream_name, line):
        """
        Do nothing
        """

    def on_end(self, returncode):
        """
        Do nothing
        """

    def on_interrupt(self):
        """
        Do nothing
        """


class SafeDelegate(IDelegate):
    """
    Delegate that checks for missing methods in another delegate

    This class is useful when your delegate is of the older type (it may just
    have the on_line method) but you don't want to provide all of the dummy
    methods.

    It is automatically used by ExternalCommandWithDelegate, Chain and
    Transform classes
    """

    def __init__(self, delegate):
        if isinstance(delegate, IDelegate):
            raise TypeError(
                "Using SafeDelegate with IDelegate subclass makes no sense")
        self._delegate = delegate

    def on_begin(self, args, kwargs):
        """
        Call on_begin() on the wrapped delegate if supported
        """
        if hasattr(self._delegate, "on_begin"):
            self._delegate.on_begin(args, kwargs)

    def on_line(self, stream_name, line):
        """
        Call on_line() on the wrapped delegate if supported
        """
        if hasattr(self._delegate, "on_line"):
            self._delegate.on_line(stream_name, line)

    def on_end(self, returncode):
        """
        Call on_end() on the wrapped delegate if supported
        """
        if hasattr(self._delegate, "on_end"):
            self._delegate.on_end(returncode)

    def on_interrupt(self):
        """
        Call on_interrupt() on the wrapped delegate if supported
        """
        if hasattr(self._delegate, "on_interrupt"):
            self._delegate.on_interrupt()

    @classmethod
    def wrap_if_needed(cls, delegate):
        """
        Wrap another delegate in SafeDelegate if needed
        """
        if isinstance(delegate, IDelegate):
            return delegate
        else:
            return cls(delegate)


class ExternalCommandWithDelegate(ExternalCommand):
    """
    The actually interesting subclass of ExternalCommand.

    Here both stdout and stderr are unconditionally captured and parsed for
    line-by-line output that is then passed to a helper delegate object.

    This allows writing 'tee' like programs that both display (with possible
    transformations) and store the output stream.

    ..note:
        Technically this class uses threads and queues to communicate which is
        very heavyweight but (yay) works portably for windows. A unix-specific
        subclass implementing this with _just_ poll could be provided with the
        same interface.

    """

    def __init__(self, delegate, killsig=signal.SIGINT):
        """
        Set the delegate helper. Technically it needs to have a 'on_line()'
        method. For actual example code look at :class:`Tee`.
        """
        self._queue = Queue()
        self._delegate = SafeDelegate.wrap_if_needed(delegate)
        self._killsig = killsig

    def call(self, *args, **kwargs):
        """
        Invoke the desired sub-process and intercept the output.
        See the description of the class for details.

        .. note:
            A very important aspect is that CTRL-C (aka KeyboardInterrupt) will
            KILL the invoked subprocess. This is handled by
            _on_keyboard_interrupt() method.
        """
        # Notify that the process is about to start
        self._delegate.on_begin(args, kwargs)
        # Setup stodut/stderr redirection
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        # Start the process
        proc = self._popen(*args, **kwargs)
        # Setup all worker threads. By now the pipes have been created and
        # proc.stdout/proc.stderr point to open pipe objects.
        stdout_reader = threading.Thread(
            target=self._read_stream, args=(proc.stdout, "stdout"))
        stderr_reader = threading.Thread(
            target=self._read_stream, args=(proc.stderr, "stderr"))
        queue_worker = threading.Thread(target=self._drain_queue)
        # Start all workers
        queue_worker.start()
        stdout_reader.start()
        stderr_reader.start()
        try:
            while True:
                try:
                    # Wait for the process to finish
                    proc.wait()
                    # Break out of the endless loop if it does
                    break
                except KeyboardInterrupt:
                    # On interrupt send a signal to the process
                    self._on_keyboard_interrupt(proc)
                    # And send a notification about this
                    self._delegate.on_interrupt()
        finally:
            # Wait until all worker threads shut down
            stdout_reader.join()
            stderr_reader.join()
            # Tell the queue worker to shut down
            self._queue.put(None)
            queue_worker.join()
        # Notify that the process has finished
        self._delegate.on_end(proc.returncode)
        return proc.returncode

    def _on_keyboard_interrupt(self, proc):
        proc.send_signal(self._killsig)

    def _read_stream(self, stream, stream_name):
        while True:
            line = stream.readline()
            if len(line) == 0:
                break
            cmd = (stream_name, line)
            self._queue.put(cmd)

    def _drain_queue(self):
        while True:
            args = self._queue.get()
            if args is None:
                break
            self._delegate.on_line(*args)


class Chain(IDelegate):
    """
    Delegate for using a chain of delegates.

    Each method is invoked for all the delegates. This make it easy to compose
    the desired effect out of a list of smaller specialized classes.
    """

    def __init__(self, delegate_list):
        """
        Construct a Chain of delegates.

        Each delegate is wrapped in :class:`SafeDelegate` if needed
        """
        self.delegate_list = [
            SafeDelegate.wrap_if_needed(delegate)
            for delegate in delegate_list]

    def on_begin(self, args, kwargs):
        """
        Call the on_begin() method on each delegate in the list
        """
        for delegate in self.delegate_list:
            delegate.on_begin(args, kwargs)

    def on_line(self, stream_name, line):
        """
        Call the on_line() method on each delegate in the list
        """
        for delegate in self.delegate_list:
            delegate.on_line(stream_name, line)

    def on_end(self, returncode):
        """
        Call the on_end() method on each delegate in the list
        """
        for delegate in self.delegate_list:
            delegate.on_end(returncode)

    def on_interrupt(self):
        """
        Call the on_interrupt() method on each delegate in the list
        """
        for delegate in self.delegate_list:
            delegate.on_interrupt()


class Redirect(DelegateBase):
    """
    Redirect each line to desired stream.
    """

    def __init__(self, stdout=None, stderr=None, close_stdout_on_end=False,
                 close_stderr_on_end=False):
        """
        Set ``stdout`` and ``stderr`` streams for writing the output to.  If
        left blank then ``sys.stdout`` and ``sys.stderr`` are used instead.
        """
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._close_stdout_on_end = close_stdout_on_end
        self._close_stderr_on_end = close_stderr_on_end

    def on_line(self, stream_name, line):
        """
        Write each line, verbatim, to the desired stream.
        """
        assert stream_name == 'stdout' or stream_name == 'stderr'
        if stream_name == 'stdout':
            self._stdout.write(line)
        else:
            self._stderr.write(line)

    def on_end(self, returncode):
        """
        Close the output streams if requested
        """
        if self._close_stdout_on_end:
            self._stdout.close()
        if self._close_stderr_on_end:
            self._stderr.close()


class Transform(DelegateBase):
    """
    Transformation filter for output lines

    Allows to transform each line before being passed down to subsequent
    delegate. The delegate is automatically wrapped in :class:`SafeDelegate` if
    needed.
    """

    def __init__(self, callback, delegate):
        """
        Set the callback and subsequent delegate.
        """
        self._callback = callback
        self._delegate = SafeDelegate.wrap_if_needed(delegate)

    def on_line(self, stream_name, line):
        """
        Transform each line by calling callback(stream_name, line) and pass it
        down to the subsequent delegate.
        """
        transformed_line = self._callback(stream_name, line)
        self._delegate.on_line(stream_name, transformed_line)


class Decode(Transform):
    """
    Decode output lines with the specified encoding

    Allows to work with Unicode strings on the inside of the application and
    bytes on the outside, as it should be. Especially useful in python 3.
    """

    def __init__(self, delegate, encoding='UTF-8'):
        """
        Set the callback and subsequent delegate.
        """
        super(Decode, self).__init__(self._decode, delegate)
        self._encoding = encoding

    def _decode(self, stream_name, line):
        """
        Decode each line with the configured encoding
        """
        return line.decode(self._encoding)


class Encode(Transform):
    """
    Encode output lines into the specified bytes encoding

    Allows to work with Unicode strings on the inside of the application and
    bytes on the outside, as it should be. Especially useful in python 3.
    """

    def __init__(self, delegate, encoding='UTF-8'):
        """
        Set the callback and subsequent delegate.
        """
        super(Encode, self).__init__(self._encode, delegate)
        self._encoding = encoding

    def _encode(self, stream_name, line):
        """
        Decode each line with the configured encoding
        """
        return line.encode(self._encoding)


class EncodeInPython2(Encode):
    """
    Encode Unicode strings to byte strings, but only in python2

    This class is kind of awkward but it solves one interesting problem in the
    python3 transition, that stdout/stderr are opened in text mode by default
    (unless redirected). This means that you can and indeed must write Unicode
    strings to that stream, not byte strings.
    """

    def _encode(self, stream_name, line):
        """
        Decode each line with the configured encoding
        """
        if sys.version_info[0] == 2:
            return line.encode(self._encoding)
        else:
            return line
