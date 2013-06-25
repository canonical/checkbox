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
:mod:`plainbox.vendor.extcmd` - subprocess with advanced output processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Unlike subprocess, which just gives you a lump of output at the end, extcmd
allows you to get callbacks (via a delegate class) on all IO.

Delegates
=========

Each delegate has four methods (on_begin, on_line, on_end, on_interrupt) but it
is possible to simply specify the ones you are interested in and extcmd will do
the right thing automatically. There is an associated interface
extcmd.IDelegate, if you subclass that class in your delegates then extcmd will
trust you do everything properly. If you pass any other object as delegate then
extcmd will wrap your object in extcmd.SafeDelegate that which provides default
implementations of all the required methods.

To make some common cases easier to work with, extcmd comes with a number of
utility callback delegates: decoding and encoding from bytes to Unicode,
transforming the data, redirecting the output to other streams and even forking
the output so that you can, for example, log and display data at the same time.


Everything is encapsulated in a single module, extcmd::

    >>> from __future__ import with_statement
    >>> import extcmd

Basic IO
========

Since IO is oriented around bytes, the first example will actually focus on
getting the basic IO work-flow right: convert bytes and Unicode at application
boundaries. Sadly Popen does not support that, let's build one that does::

    >>> unicode_popen = extcmd.ExternalCommandWithDelegate(
    ...     extcmd.Decode(
    ...         extcmd.EncodeInPython2(
    ...             extcmd.Redirect())))

So this may be somewhat hard to read but the basic looks like this:

We instantiate the ExtrnalCommandWithDelegate, this is like subprocess.Popen
metaclass as the return value is something we can use to actually run call() or
check_call(). The only argument to that is a single delegate object. We'll use
three of the delegates provided by extcmd here.

The Decode delegate simply decodes all IO from a specified encoding (uses UTF-8
by default). The Encode delegate does the reverse (which is a real no-op but
we'll grow this example in a second and it will be useful to have Unicode
strings then). Lastly the Redirect delegate sends all of stdout/stderr back to
real stdout/stderr (it is also flexible so you can redirect to file or any
other stream but we're using the defaults again).

All those delegates are connected so one delegate gives the output to another
delegate. In practice it looks like this::

    (real data from the process) -> Decode -> Encode -> Redirect

Let's see how that works now:

    >>> returncode = unicode_popen.call(["echo", "zażółć gęsią jaźń"])
    zażółć gęsią jaźń

Well that was boring, but the point here is that id did _not_ crash on any
UnicodeDecodeErrors and I actually used some non-ASCII characters.

One thing worth pointing out is that unlike in subprocess, each call() returns
the process exit code::

    >>> returncode
    0

Using Transform delegate
========================

So now we have the basics. Let's explore further. The Transform delegate
allows one to call a user specified function on each line of the output.

As before we'll build a list of participating delegate objects, we'll start
with the Decode delegate, then the Transform delegate, the Encode and lastly,
Redirect. This will look like this:

    (output from process) -> Decode -> Transform -> Encode -> Redirect

For clarity we'll define the transformation first::

    >>> def transform_fn(stream_name, line):
    ...     return "{0}: {1}".format(stream_name, line)

Then build the actual stack of delegates::

    >>> delegate = extcmd.Decode(
    ...     extcmd.Transform(transform_fn,
    ...         extcmd.EncodeInPython2(
    ...             extcmd.Redirect())))
    >>> transform_popen = extcmd.ExternalCommandWithDelegate(delegate)
    >>> returncode = transform_popen.call(["echo", "hello"])
    stdout: hello

Simple Unicode-aware sed(1)
===========================

Let's build a simple in sed(1) like program. We'll use the 're' module to
actually transform text. Let's import it now::

    >>> import re

Let's define another transformation function:

    >>> def transform_fn(stream_name, line):
    ...     return re.sub("Hello", "Goodbye", line)

And plug it into the stack we've used before:

    >>> delegate = extcmd.Decode(
    ...     extcmd.Transform(transform_fn,
    ...         extcmd.EncodeInPython2(
    ...             extcmd.Redirect())))
    >>> sed_popen = extcmd.ExternalCommandWithDelegate(delegate)
    >>> returncode = sed_popen.call(["echo", "Hello World"])
    Goodbye World

Simple tee(1)
=============

Ok, so one more example, this time tee(1)-like program. This pattern can be
used to build various kinds of programs where many consumers get to see the
data that was read.

We'll use one more delegate this time, the extcmd.Chain (which is, from
retrospective, rather unfortunately named, as it's really a "fork" while
regular delegates build a chain themselves).

So this example will save everything written to stdout to a log file, while
still displaying it back to the user::

    >>> delegate = extcmd.Chain([
    ...     extcmd.Decode(
    ...         extcmd.EncodeInPython2(
    ...             extcmd.Redirect())),
    ...     extcmd.Redirect(
    ...         stdout=open("stdout.log", "wb"),
    ...         close_stdout_on_end=True)
    ... ])
    >>> tee_popen = extcmd.ExternalCommandWithDelegate(delegate)
    >>> returncode = tee_popen.call(['echo', "Hello Tee!"])
    Hello Tee!

So this example is actually more interesting, unlike before we don't decode
_all_ data, only the data that is displayed, the stdout.log file will contain a
verbatim copy of all the bytes that were produced by the called process::

    >>> import os
    >>> assert os.path.exists("stdout.log")
    >>> with open("stdout.log", "rt") as stream:
    ...     stream.read()
    'Hello Tee!\\n'
    >>> os.remove("stdout.log")

Misc stuff
==========

Apart from ExtrnalCommandWithDelegate there is a base class called
ExternalCommand that simply helps if you want to subclass and override the
call() method.

There is also the check_call() method that behaves exactly as in the subprocess
module, by raising subprocess.CalledProcessError exception on a non-zero return
code

    >>> extcmd.ExternalCommand().check_call(['false'])
    ... # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    CalledProcessError: Command '['false']' returned non-zero exit status 1

If you don't use check_call You can also look at the return code that is
returned from each call(). The returncode is also passed to each delegate that
supports the on_end() method::


    >>> import sys
    >>> class ReturnCode(extcmd.DelegateBase):
    ...     def on_end(self, returncode):
    ...         sys.stdout.write("Return code is %s\\n" % returncode)
    >>> returncode = extcmd.ExternalCommandWithDelegate(ReturnCode()).call(['false'])
    Return code is 1
    >>> returncode
    1

Each started program is also passed to the on_start() method::

    >>> import sys
    >>> class VerboseStart(extcmd.DelegateBase):
    ...     def on_begin(self, args, kwargs):
    ...         sys.stdout.write("Starting %r %r\\n" % (args, kwargs))
    >>> returncode = extcmd.ExternalCommandWithDelegate(VerboseStart()).call(['true'])
    Starting (['true'],) {}
"""

__version__ = (1, 0, 1, "final", 0)

from queue import Queue
import abc
import errno
import logging
import signal
import subprocess
import sys
import threading
try:
    import posix
except ImportError:
    posix = None


_logger = logging.getLogger("extcmd")


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

    def __repr__(self):
        return "<{0} wrapping {1!r}>".format(
            self.__class__.__name__, self._delegate)

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
        proc = None
        stdout_reader = None
        stderr_reader = None
        queue_worker = None
        try:
            # Start the process
            _logger.debug("Starting process %r", (args,))
            proc = self._popen(*args, **kwargs)
            _logger.debug("Process created: %r (pid: %d)", proc, proc.pid)
            # Setup all worker threads. By now the pipes have been created and
            # proc.stdout/proc.stderr point to open pipe objects.
            stdout_reader = threading.Thread(
                target=self._read_stream, name='stdout_reader',
                args=(proc.stdout, "stdout"))
            stderr_reader = threading.Thread(
                target=self._read_stream, name='stderr_reader',
                args=(proc.stderr, "stderr"))
            queue_worker = threading.Thread(
                target=self._drain_queue, name='queue_worker')
            # Start all workers
            _logger.debug("Starting thread: %r", queue_worker)
            queue_worker.start()
            _logger.debug("Starting thread: %r", stdout_reader)
            stdout_reader.start()
            _logger.debug("Starting thread: %r", stderr_reader)
            stderr_reader.start()
            while True:
                try:
                    # Wait for the process to finish
                    _logger.debug("Waiting for process to exit")
                    return_code = proc.wait()
                    _logger.debug(
                        "Process did exit with code %d", return_code)
                    # Break out of the endless loop if it does
                    break
                except KeyboardInterrupt:
                    _logger.debug("KeyboardInterrupt in call()")
                    # On interrupt send a signal to the process
                    self._on_keyboard_interrupt(proc)
                    # And send a notification about this
                    self._delegate.on_interrupt()
        finally:
            # Wait until all worker threads shut down
            _logger.debug("Joining all threads...")
            if stdout_reader is not None:
                _logger.debug("Closing child stdout")
                proc.stdout.close()
                _logger.debug("Joining 1/3 %r...", stdout_reader)
                stdout_reader.join()
                _logger.debug("Joined thread: %r", stdout_reader)
            if stderr_reader is not None:
                _logger.debug("Closing child stderr")
                proc.stderr.close()
                _logger.debug("Joining 2/3 %r...", stderr_reader)
                stderr_reader.join()
                _logger.debug("Joined thread: %r", stderr_reader)
            if queue_worker is not None:
                # Tell the queue worker to shut down
                _logger.debug("Telling queue_worker thread to exit")
                self._queue.put(None)
                _logger.debug("Joining 3/3 %r...", queue_worker)
                queue_worker.join()
                _logger.debug("Joined thread: %r", queue_worker)
        # Notify that the process has finished
        self._delegate.on_end(proc.returncode)
        return proc.returncode

    def _on_keyboard_interrupt(self, proc):
        _logger.debug("Sending signal %s to the process", self._killsig)
        try:
            proc.send_signal(self._killsig)
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                pass
                _logger.debug(
                    "Cannot deliver signal %d, the process gone",
                    self._killsig)
            else:
                raise

    def _read_stream(self, stream, stream_name):
        _logger.debug("_read_stream(%r, %r) entering", stream, stream_name)
        while True:
            try:
                line = stream.readline()
            except (IOError, ValueError):
                # Ignore IOError and ValueError that may be raised if
                # the stream was closed this can happen if the process exits
                # very quickly without printing anything and the cleanup code
                # starts to close both of the streams
                break
            else:
                if len(line) == 0:
                    break
                cmd = (stream_name, line)
                self._queue.put(cmd)
        _logger.debug("_read_stream(%r, %r) exiting", stream, stream_name)

    def _drain_queue(self):
        _logger.debug("_drain_queue() entering")
        while True:
            args = self._queue.get()
            if args is None:
                break
            self._delegate.on_line(*args)
        _logger.debug("_drain_queue() exiting")


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

    def __repr__(self):
        return "<{0} {1!r}>".format(
            self.__class__.__name__, self.delegate_list)

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

    def __repr__(self):
        return "<{0} stdout:{1!r} stderr:{2!r}>".format(
            self.__class__.__name__,
            self._stdout, self._stderr)

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

    def __repr__(self):
        return "<{0} callback:{1!r} delegate:{2!r}>".format(
            self.__class__.__name__, self._callback, self._delegate)

    def on_line(self, stream_name, line):
        """
        Transform each line by calling callback(stream_name, line) and pass it
        down to the subsequent delegate.
        """
        transformed_line = self._callback(stream_name, line)
        self._delegate.on_line(stream_name, transformed_line)

    def on_begin(self, args, kwargs):
        self._delegate.on_begin(args, kwargs)

    def on_end(self, returncode):
        self._delegate.on_end(returncode)


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

    def __repr__(self):
        return "<{0} encoding:{1!r} delegate:{2!r}>".format(
            self.__class__.__name__, self._encoding, self._delegate)

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

    def __repr__(self):
        return "<{0} encoding:{1!r} delegate:{2!r}>".format(
            self.__class__.__name__, self._encoding, self._delegate)

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
