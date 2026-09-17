import os
import selectors
import subprocess as sp
import sys
from collections import deque


def stream_process_output(
    process: "sp.Popen[str]",
    stdout_maxlen: "int | None" = 10,
    stderr_maxlen: "int | None" = 10,
    print_stdout: bool = True,
    print_stderr: bool = True,
) -> "tuple[list[str], list[str]]":
    """
    Drain a process' stdout and stderr concurrently without threads
    - streams output live to the current stdout and stderr so the subprocess
    doesn't look frozen

    :param process: an sp.Popen with stdout=PIPE, stderr=PIPE
    :param stdout_lines: how many trailing stdout lines to keep and
        return, or None to keep everything
    :param stderr_lines: how many trailing stderr lines to keep and
        return, or None to keep everything
    :param print_stdout: print each stdout line to console as it arrives
    :param print_stderr: print each stderr line to console as it arrives
    :return: (trailing stdout lines, trailing stderr lines)
    """
    # they should be io.TextIO objects
    if not (process.stdout and process.stderr):
        raise RuntimeError(
            "Both stdout and stderr must be subprocess.PIPE to use this function"
        )

    stdout_fd = process.stdout.fileno()
    stderr_fd = process.stderr.fileno()
    
    os.set_blocking(stdout_fd, False)
    os.set_blocking(stderr_fd, False)

    sel = selectors.DefaultSelector()
    sel.register(stdout_fd, selectors.EVENT_READ)
    sel.register(stderr_fd, selectors.EVENT_READ)

    # raw byte buffer per fd, holding an incomplete trailing line
    pending: "dict[int, bytes]" = {stdout_fd: b"", stderr_fd: b""}
    open_fds = {stdout_fd, stderr_fd}
    lines: "dict[int, deque[str]]" = {
        stdout_fd: deque(maxlen=stdout_maxlen),
        stderr_fd: deque(maxlen=stderr_maxlen),
    }

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
                continue

            pending[fd] += chunk
            *complete, pending[fd] = pending[fd].split(b"\n")
            for raw_line in complete:
                clean_line = raw_line.decode(errors="replace").strip()
                if fd == stdout_fd and print_stdout:
                    print(clean_line, flush=True)
                if fd == stderr_fd and print_stderr:
                    print(clean_line, flush=True, file=sys.stderr)
                lines[fd].append(clean_line)

    # flush a final line on each stream that never got a trailing newline
    for fd in (stdout_fd, stderr_fd):
        if pending[fd]:
            clean_line = pending[fd].decode(errors="replace").strip()
            if fd == stdout_fd and print_stdout:
                print(clean_line, flush=True)
            if fd == stderr_fd and print_stderr:
                print(clean_line, flush=True, file=sys.stderr)
            lines[fd].append(clean_line)

    process.wait()
    return list(lines[stdout_fd]), list(lines[stderr_fd])
