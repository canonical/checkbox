import codecs
import io
import os
import selectors
import subprocess as sp
import sys
import time
from collections import deque
from typing import Never

# max characters buffered for a single line before we forcefully emit it
MAX_PENDING_CHARS = 65536


def stream_process_output(
    process: "sp.Popen[str]",
    stdout_maxlen: "int | None" = 10,
    stderr_maxlen: "int | None" = 10,
    print_stdout: bool = True,
    print_stderr: bool = True,
    timeout: "float | None" = None,
) -> "tuple[int, list[str], list[str]]":
    """Streams subprocess stderr and stdout live to the current stdout and stderr
    so the subprocess doesn't look frozen.

    WARNING: Caller is responsible for ensuring process.wait() hasn't been called
    process.stdout and process.stderr are closed when this function returns.

    Example usage:
    ```py
    some_slow_proc = subprocess.Popen([...])
    rc, stdout_lines, stderr_lines = stream_process_output(some_slow_proc)
    ```

    :param process: an sp.Popen with stdout=PIPE, stderr=PIPE, universal_newlines=True
    :param stdout_maxlen:
        how many stdout lines to keep.
        Keep everything if None
    :param stderr_maxlen:
        how many stderr lines to keep.
        Keep everything if None
    :param print_stdout: stream to caller's stdout?
    :param print_stderr: stream to caller's stderr?
    :param timeout:
        seconds to wait for the process to finish. On expiry the process
        is killed. Wait forever if None
    :raises TypeError: stdout is not TextIO
    :raises TypeError: stderr is not TextIO
    :raises subprocess.TimeoutExpired:
        the timeout expired, output and stderr hold the kept lines
    :return: return code, stdout lines, stderr lines
    """

    if not isinstance(process.stdout, io.TextIOBase):
        raise TypeError(
            "Process stdout must be set to subprocess.PIPE during creation "
            + f"to use this function. Got {type(process.stdout)}"
        )

    if not isinstance(process.stderr, io.TextIOBase):
        raise TypeError(
            "Process stderr must be set to subprocess.PIPE during creation "
            + f"to use this function. Got {type(process.stderr)}"
        )

    stdout_fd = process.stdout.fileno()
    stderr_fd = process.stderr.fileno()

    os.set_blocking(stdout_fd, False)
    os.set_blocking(stderr_fd, False)

    # register read events
    # so we can respond when something appears in the fd
    sel = selectors.DefaultSelector()
    sel.register(stdout_fd, selectors.EVENT_READ)
    sel.register(stderr_fd, selectors.EVENT_READ)

    # decode with each stream's own encoding (os.read bypasses the
    # TextIOWrapper), always replacing undecodable bytes instead of raising
    decoders = {
        fd: codecs.getincrementaldecoder(stream.encoding)(errors="replace")
        for fd, stream in (
            (stdout_fd, process.stdout),
            (stderr_fd, process.stderr),
        )
    }
    # pieces of the current unterminated line, capped at MAX_PENDING_CHARS
    # newline="" disables newline translation to keep \r
    pending = {
        stdout_fd: io.StringIO(newline=""),
        stderr_fd: io.StringIO(newline=""),
    }
    open_fds = {stdout_fd, stderr_fd}
    lines: "dict[int, deque[str]]" = {
        stdout_fd: deque(maxlen=stdout_maxlen),
        stderr_fd: deque(maxlen=stderr_maxlen),
    }

    def emit_lines(fd: int, line: str):
        clean_line = line.rstrip()  # preserve leading whitespace
        if fd == stdout_fd and print_stdout:
            print(clean_line, flush=True)
        if fd == stderr_fd and print_stderr:
            print(clean_line, flush=True, file=sys.stderr)
        lines[fd].append(clean_line)

    def flush_pending(fd: int):
        emit_lines(fd, pending[fd].getvalue())
        # let the garbage collector clean up for us
        pending[fd] = io.StringIO(newline="")

    def feed(fd: int, text: str):
        *complete, rest = text.split("\n")
        if complete:
            pending[fd].write(complete[0])
            flush_pending(fd)
            for line in complete[1:]:
                emit_lines(fd, line)
        if rest:
            pending[fd].write(rest)
            # tell() is the number of chars buffered since the last flush
            if pending[fd].tell() >= MAX_PENDING_CHARS:
                # cap very long lines
                # or output with no newline like snapd \r spinners
                # emit what we have so memory stays bounded
                flush_pending(fd)

    deadline = None if timeout is None else time.monotonic() + timeout

    def time_remaining() -> "float | None":
        if deadline is None:
            return None
        return max(0.0, deadline - time.monotonic())

    def flush_all_pending():
        # flush a final line on each stream that never got a trailing newline
        for fd in (stdout_fd, stderr_fd):
            if pending[fd].tell():
                flush_pending(fd)

    def kill_and_raise() -> "Never":
        assert timeout is not None
        flush_all_pending()
        process.kill()
        process.wait()
        raise sp.TimeoutExpired(
            process.args,
            timeout,
            output="\n".join(lines[stdout_fd]),
            stderr="\n".join(lines[stderr_fd]),
        )

    try:
        while open_fds:
            # always check timeout before the stdout/stderr events
            # to make sure we can still kill noisy processes
            if time_remaining() == 0:
                kill_and_raise()

            for key, _ in sel.select(timeout=time_remaining()):
                fd = key.fd
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    # selector said readable, but nothing left right now
                    continue

                if not chunk:
                    # EOF on this pipe, the process closed it
                    sel.unregister(fd)
                    open_fds.discard(fd)
                    feed(fd, decoders[fd].decode(b"", final=True))
                    continue

                feed(fd, decoders[fd].decode(chunk))
    finally:
        sel.close()
        # like communicate(), we now own the pipes
        # so we need to manually close them
        process.stdout.close()
        process.stderr.close()

    flush_all_pending()

    try:
        # the process may close its pipes but keep running
        rc = process.wait(timeout=time_remaining())
    except sp.TimeoutExpired:
        kill_and_raise()

    return rc, list(lines[stdout_fd]), list(lines[stderr_fd])
