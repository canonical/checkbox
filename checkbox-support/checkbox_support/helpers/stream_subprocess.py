import codecs
import io
import os
import selectors
import subprocess as sp
import sys
from collections import deque

# max characters buffered for a single line before we forcefully emit it
MAX_PENDING_CHARS = 65536


def stream_process_output(
    process: "sp.Popen[str]",
    stdout_maxlen: "int | None" = 10,
    stderr_maxlen: "int | None" = 10,
    print_stdout: bool = True,
    print_stderr: bool = True,
) -> "tuple[int, list[str], list[str]]":
    """
    Streams subprocess stderr and stdout live to the current stdout and stderr
    so the subprocess doesn't look frozen.

    WARNING: Caller is responsible for ensuring process.wait() hasn't been called

    Example usage:
    ```py
    some_slow_proc = subprocess.Popen([...])
    rc, stdout_lines, stderr_lines = stream_process_output(some_slow_proc)
    ```

    :param process: an sp.Popen with stdout=PIPE, stderr=PIPE
    :param stdout_lines: how many trailing stdout lines to keep and
        return, or None to keep everything
    :param stderr_lines: how many trailing stderr lines to keep and
        return, or None to keep everything
    :param print_stdout: print each stdout line to console as it arrives
    :param print_stderr: print each stderr line to console as it arrives
    :return: (return code, recent stdout lines, recent stderr lines)
    """
    # they should be io.TextIO objects
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

    def emit(fd: int, line: str):
        clean_line = line.strip()
        if fd == stdout_fd and print_stdout:
            print(clean_line, flush=True)
        if fd == stderr_fd and print_stderr:
            print(clean_line, flush=True, file=sys.stderr)
        lines[fd].append(clean_line)

    def flush_pending(fd: int):
        emit(fd, pending[fd].getvalue())
        # let the garbage collector clean up for us
        pending[fd] = io.StringIO(newline="")

    def feed(fd: int, text: str):
        *complete, rest = text.split("\n")
        if complete:
            pending[fd].write(complete[0])
            flush_pending(fd)
            for line in complete[1:]:
                emit(fd, line)
        if rest:
            pending[fd].write(rest)
            # tell() is the number of chars buffered since the last flush
            if pending[fd].tell() >= MAX_PENDING_CHARS:
                # cap very long lines
                # or output with no newline like snapd \r spinners
                # emit what we have so memory stays bounded
                flush_pending(fd)

    while open_fds:
        for key, _ in sel.select():
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

    # flush a final line on each stream that never got a trailing newline
    for fd in (stdout_fd, stderr_fd):
        if pending[fd].tell():
            flush_pending(fd)

    rc = process.wait()
    return rc, list(lines[stdout_fd]), list(lines[stderr_fd])
