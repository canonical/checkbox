"""
Tests for stream_proc.stream_process_output focused on:
- running the function inside worker threads (not just the main thread)
- "hysterical" subprocesses: huge stderr floods, bare \\r spinner output with
  no trailing newline, garbage/invalid bytes, and processes that die abruptly

All subprocesses are spawned with `python3 -c "..."` so the tests have no
external dependencies.
"""
import subprocess as sp
import sys
import threading
import time
import unittest as ut
from typing import Any

from checkbox_support.helpers.stream_subprocess import stream_process_output


def make_proc(code: str) -> "sp.Popen[str]":
    return sp.Popen(
        [sys.executable, "-c", code],
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
    )


class TestRunningInSeparateThread(ut.TestCase):

    def test_runs_correctly_in_a_background_thread(self):
        """The function uses selectors (not signals), so it must work fine when
        invoked from a non-main thread."""
        proc = make_proc(
            "import sys\n"
            "for i in range(50):\n"
            "    print(f'out-{i}')\n"
            "    print(f'err-{i}', file=sys.stderr)\n"
        )

        result = {}

        def worker():
            result["out"], result["err"] = stream_process_output(
                proc, stdout_maxlen=None, stderr_maxlen=None,
                print_stdout=False, print_stderr=False,
            )

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)

        assert not t.is_alive(), "stream_process_output hung/deadlocked in a thread"
        assert result["out"] == [f"out-{i}" for i in range(50)]
        assert result["err"] == [f"err-{i}" for i in range(50)]
        assert proc.returncode == 0


    def test_multiple_concurrent_threads_each_draining_own_subprocess(self):
        """Several threads each streaming a different subprocess concurrently
        should not interfere with each other (no shared global selector state
        leaking between calls)."""
        n_threads = 8
        results: 'list[Any]' = [None] * n_threads
        errors = []

        def worker(idx):
            try:
                proc = make_proc(f"print('hello-{idx}')")
                out, _ = stream_process_output(
                    proc, print_stdout=False, print_stderr=False
                )
                results[idx] = out
            except Exception as e:  # pragma: no cover - failure surfaced via assert
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert all(not t.is_alive() for t in threads)
        for i in range(n_threads):
            assert results[i] == [f"hello-{i}"]


    def test_caller_thread_not_blocked_forever_by_slow_subprocess(self):
        """A subprocess that trickles output slowly should still be drained
        without the calling thread spinning/burning CPU or hanging past the
        subprocess's own runtime."""
        proc = make_proc(
            "import time\n"
            "for i in range(3):\n"
            "    print(i, flush=True)\n"
            "    time.sleep(0.2)\n"
        )
        start = time.monotonic()
        out, _ = stream_process_output(proc, print_stdout=False, print_stderr=False)
        elapsed = time.monotonic() - start

        assert out == ["0", "1", "2"]
        # should roughly track the ~0.6s of sleeping, not hang indefinitely
        assert elapsed < 5


class TestHystericalSubprocesses(ut.TestCase):

    def test_bare_carriage_return_spinner_with_no_newline(self):
        """Progress-bar style output that only uses \\r (never \\n) is never
        split into multiple lines by this function (it only splits on b'\\n'),
        so it should arrive as one single trailing line, with the embedded \\r
        characters intact except for the final .strip() trim."""
        proc = make_proc(
            "import sys, time\n"
            "for i in range(20):\n"
            "    sys.stdout.write(f'\\rprogress {i}/20')\n"
            "    sys.stdout.flush()\n"
            "    time.sleep(0.01)\n"
        )
        out, _ = stream_process_output(proc, print_stdout=False, print_stderr=False)

        assert len(out) == 1
        # strip() only removes leading/trailing whitespace, so internal \r's
        # from earlier writes remain embedded in the final flushed line.
        assert out[0].endswith("progress 19/20")
        assert "\r" in out[0]


    def test_crlf_line_endings_are_stripped_cleanly(self):
        """\\r\\n endings should collapse to clean lines because .strip() trims
        the trailing \\r left over after splitting on \\n."""
        proc = make_proc(
            "import sys\n"
            "sys.stdout.write('line1\\r\\nline2\\r\\n')\n"
        )
        out, _ = stream_process_output(proc, print_stdout=False, print_stderr=False)
        assert out == ["line1", "line2"]


    def test_massive_stderr_flood_does_not_deadlock_or_lose_stdout(self):
        """A subprocess that dumps megabytes to stderr rapidly while stdout is
        comparatively quiet must not deadlock (this is exactly what the
        selectors-based design is meant to prevent vs. naive sequential reads)."""
        proc = make_proc(
            "import sys\n"
            "print('stdout-line')\n"
            "for i in range(200000):\n"
            "    print('E' * 100, file=sys.stderr)\n"
            "print('stdout-line-2')\n"
        )
        start = time.monotonic()
        out, err = stream_process_output(
            proc, stdout_maxlen=None, stderr_maxlen=5,
            print_stdout=False, print_stderr=False,
        )
        elapsed = time.monotonic() - start

        assert elapsed < 30, "likely deadlocked on a filled pipe"
        assert out == ["stdout-line", "stdout-line-2"]
        assert len(err) == 5  # maxlen truncation kept only the trailing lines
        assert all(line == "E" * 100 for line in err)
        assert proc.returncode == 0


    def test_rapid_interleaved_stdout_and_stderr(self):
        """High-frequency interleaved writes on both streams should all be
        captured without corruption or cross-stream mixing."""
        proc = make_proc(
            "import sys\n"
            "for i in range(5000):\n"
            "    print(f'o{i}')\n"
            "    print(f'e{i}', file=sys.stderr)\n"
        )
        out, err = stream_process_output(
            proc, stdout_maxlen=None, stderr_maxlen=None,
            print_stdout=False, print_stderr=False,
        )
        assert out == [f"o{i}" for i in range(5000)]
        assert err == [f"e{i}" for i in range(5000)]


    def test_invalid_utf8_bytes_are_replaced_not_fatal(self):
        """Garbage / non-UTF8 bytes on the wire must not raise; decode uses
        errors='replace'."""
        proc = sp.Popen(
            [sys.executable, "-c", (
                "import sys\n"
                "sys.stdout.buffer.write(b'good\\xff\\xfeline\\n')\n"
                "sys.stdout.buffer.flush()\n"
            )],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            text=True,
        )
        out, _ = stream_process_output(proc, print_stdout=False, print_stderr=False)
        assert len(out) == 1
        assert "good" in out[0] and "line" in out[0]


    def test_process_dies_abruptly_mid_stream_still_returns(self):
        """A subprocess that gets killed/crashes partway through (pipes close
        with no final newline) should still return promptly with whatever was
        captured, not hang."""
        proc = make_proc(
            "import sys, os\n"
            "print('before-crash', flush=True)\n"
            "sys.stdout.write('partial-no-newline')\n"
            "sys.stdout.flush()\n"
            "os._exit(1)\n"
        )
        out, _ = stream_process_output(proc, print_stdout=False, print_stderr=False)
        assert out == ["before-crash", "partial-no-newline"]
        assert proc.returncode == 1


    def test_maxlen_zero_and_small_bound_under_flood(self):
        """stdout_maxlen/stderr_maxlen bound memory even under a flood; verify
        a very small maxlen keeps only the most recent lines."""
        proc = make_proc(
            "for i in range(10000):\n"
            "    print(i)\n"
        )
        out, _ = stream_process_output(
            proc, stdout_maxlen=1, print_stdout=False, print_stderr=False
        )
        assert out == ["9999"]



