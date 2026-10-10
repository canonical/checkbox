import select
import selectors
import subprocess as sp
import sys
import threading
import time
import unittest as ut
from typing import Any
from unittest import mock

from checkbox_support.helpers.stream_subprocess import (
    MAX_PENDING_CHARS,
    stream_process_output,
)


def make_proc(code: str) -> "sp.Popen[str]":
    return sp.Popen(
        [sys.executable, "-c", code],
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        universal_newlines=True,
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
            result["rc"], result["out"], result["err"] = stream_process_output(
                proc,
                stdout_maxlen=None,
                stderr_maxlen=None,
                print_stdout=False,
                print_stderr=False,
            )

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)

        self.assertFalse(
            t.is_alive(), "stream_process_output hung/deadlocked in a thread"
        )
        self.assertEqual(result["out"], [f"out-{i}" for i in range(50)])
        self.assertEqual(result["err"], [f"err-{i}" for i in range(50)])
        self.assertEqual(result["rc"], 0)
        self.assertEqual(proc.returncode, 0)

    def test_multiple_concurrent_threads_each_draining_own_subprocess(self):
        """Several threads each streaming a different subprocess concurrently
        should not interfere with each other (no shared global selector state
        leaking between calls)."""
        n_threads = 8
        results: "list[Any]" = [None] * n_threads
        errors = []

        def worker(idx):
            try:
                proc = make_proc(f"print('hello-{idx}')")
                rc, out, _ = stream_process_output(
                    proc, print_stdout=False, print_stderr=False
                )
                results[idx] = (rc, out)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertFalse(errors)
        self.assertFalse(any(t.is_alive() for t in threads))
        for i in range(n_threads):
            self.assertEqual(results[i], (0, [f"hello-{i}"]))

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
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        elapsed = time.monotonic() - start

        self.assertEqual(out, ["0", "1", "2"])
        # should roughly track the ~0.6s of sleeping, not hang indefinitely
        self.assertLess(elapsed, 5)


class TestHystericalSubprocesses(ut.TestCase):

    def test_bare_carriage_return_spinner_with_no_newline(self):
        """Progress-bar style output that only uses \\r (never \\n) is never
        split into multiple lines by this function (it only splits on b'\\n'),
        so it should arrive as one single trailing line, with the embedded \\r
        characters intact except for the final .rstrip() trim."""
        proc = make_proc(
            "import sys, time\n"
            "for i in range(20):\n"
            "    sys.stdout.write(f'\\rprogress {i}/20')\n"
            "    sys.stdout.flush()\n"
            "    time.sleep(0.01)\n"
        )
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )

        self.assertEqual(len(out), 1)
        # rstrip() only removes trailing whitespace, so internal \r's
        # from earlier writes remain embedded in the final flushed line.
        self.assertTrue(out[0].endswith("progress 19/20"))
        self.assertIn("\r", out[0])

    def test_crlf_line_endings_are_stripped_cleanly(self):
        """\\r\\n endings should collapse to clean lines because .rstrip()
        trims the trailing \\r left over after splitting on \\n."""
        proc = make_proc(
            "import sys\n" "sys.stdout.write('line1\\r\\nline2\\r\\n')\n"
        )
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, ["line1", "line2"])

    def test_leading_whitespace_is_preserved(self):
        """Indentation must survive so tracebacks and column-aligned output
        are shown and returned faithfully."""
        proc = make_proc(
            "import sys\n"
            "print('    four spaces')\n"
            "print('\\ttab')\n"
            "print('  two spaces', file=sys.stderr)\n"
        )
        _, out, err = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, ["    four spaces", "\ttab"])
        self.assertEqual(err, ["  two spaces"])

    def test_massive_stderr_flood_does_not_deadlock_or_lose_stdout(self):
        """A subprocess that dumps megabytes to stderr rapidly while stdout is
        comparatively quiet must not deadlock (this is exactly what the
        selectors-based design is meant to prevent vs. naive sequential reads).
        """
        proc = make_proc(
            "import sys\n"
            "print('stdout-line')\n"
            "for i in range(200000):\n"
            "    print('E' * 100, file=sys.stderr)\n"
            "print('stdout-line-2')\n"
        )
        start = time.monotonic()
        rc, out, err = stream_process_output(
            proc,
            stdout_maxlen=None,
            stderr_maxlen=5,
            print_stdout=False,
            print_stderr=False,
        )
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 30, "likely deadlocked on a filled pipe")
        self.assertEqual(out, ["stdout-line", "stdout-line-2"])
        # maxlen truncation kept only the trailing lines
        self.assertEqual(err, ["E" * 100] * 5)
        self.assertEqual(rc, 0)
        self.assertEqual(proc.returncode, 0)

    def test_rapid_interleaved_stdout_and_stderr(self):
        """High-frequency interleaved writes on both streams should all be
        captured without corruption or cross-stream mixing."""
        proc = make_proc(
            "import sys\n"
            "for i in range(5000):\n"
            "    print(f'o{i}')\n"
            "    print(f'e{i}', file=sys.stderr)\n"
        )
        _, out, err = stream_process_output(
            proc,
            stdout_maxlen=None,
            stderr_maxlen=None,
            print_stdout=False,
            print_stderr=False,
        )
        self.assertEqual(out, [f"o{i}" for i in range(5000)])
        self.assertEqual(err, [f"e{i}" for i in range(5000)])

    def test_invalid_utf8_bytes_are_replaced_not_fatal(self):
        """Garbage / non-UTF8 bytes on the wire must not raise; decode uses
        errors='replace'."""
        proc = sp.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys\n"
                    "sys.stdout.buffer.write(b'good\\xff\\xfeline\\n')\n"
                    "sys.stdout.buffer.flush()\n"
                ),
            ],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            universal_newlines=True,
        )
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(len(out), 1)
        self.assertIn("good", out[0])
        self.assertIn("line", out[0])

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
        rc, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, ["before-crash", "partial-no-newline"])
        self.assertEqual(rc, 1)
        self.assertEqual(proc.returncode, 1)

    def test_maxlen_zero_and_small_bound_under_flood(self):
        """stdout_maxlen/stderr_maxlen bound memory even under a flood; verify
        a very small maxlen keeps only the most recent lines."""
        proc = make_proc("for i in range(10000):\n" "    print(i)\n")
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=1, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, ["9999"])

    def test_both_streams_flood_without_newlines(self):
        """Both pipes spewing megabytes with no newline at the same time must
        not deadlock, and every character must arrive in bounded chunks."""
        total = MAX_PENDING_CHARS * 20
        proc = make_proc(
            "import sys, threading\n"
            "t = threading.Thread(\n"
            f"    target=sys.stderr.write, args=('e' * {total},)\n"
            ")\n"
            "t.start()\n"
            f"sys.stdout.write('o' * {total})\n"
            "t.join()\n"
        )
        rc, out, err = stream_process_output(
            proc,
            stdout_maxlen=None,
            stderr_maxlen=None,
            print_stdout=False,
            print_stderr=False,
            timeout=30,
        )
        self.assertEqual(rc, 0)
        self.assertEqual("".join(out), "o" * total)
        self.assertEqual("".join(err), "e" * total)
        self.assertTrue(all(len(c) < MAX_PENDING_CHARS * 2 for c in out))
        self.assertTrue(all(len(c) < MAX_PENDING_CHARS * 2 for c in err))

    def test_single_huge_write_with_many_lines(self):
        """One multi-megabyte write() must be split into exactly its lines."""
        n = 200000
        proc = make_proc(
            "import sys\n"
            f"sys.stdout.write(''.join(f'{{i}}\\n' for i in range({n})))\n"
        )
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, [str(i) for i in range(n)])

    def test_only_newlines(self):
        """A flood of empty lines is kept as empty strings, not dropped."""
        proc = make_proc("import sys\nsys.stdout.write('\\n' * 10000)\n")
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, [""] * 10000)

    def test_no_output_at_all(self):
        proc = make_proc("import sys\nsys.exit(3)\n")
        self.assertEqual(
            stream_process_output(
                proc, print_stdout=False, print_stderr=False
            ),
            (3, [], []),
        )

    def test_long_line_then_normal_line(self):
        """A line longer than the cap is chunked, but the line after it must
        still be emitted on its own."""
        proc = make_proc(
            f"print('x' * {MAX_PENDING_CHARS * 3})\n" "print('after')\n"
        )
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out[-1], "after")
        self.assertEqual("".join(out[:-1]), "x" * MAX_PENDING_CHARS * 3)

    def test_whitespace_at_chunk_boundaries_is_kept(self):
        """Forced chunks of a long line are not line ends, so whitespace that
        lands on a chunk boundary must not be trimmed."""
        # not a multiple of the cap, so a real final line remains at EOF
        n = MAX_PENDING_CHARS * 2 + 1
        proc = make_proc(f"import sys\nsys.stdout.write('a ' * {n})\n")
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        self.assertGreater(len(out), 1)
        # only the real end of the line gets its trailing space trimmed
        self.assertEqual("".join(out), ("a " * n).rstrip())

    def test_multibyte_flood_without_newlines(self):
        """Forced chunking and os.read boundaries must never split a
        multibyte character into replacement characters."""
        total = MAX_PENDING_CHARS * 5
        proc = make_proc(
            "import sys\n" f"sys.stdout.write('é€😀' * {total // 3})\n"
        )
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        joined = "".join(out)
        self.assertNotIn("\ufffd", joined)
        self.assertEqual(joined, "é€😀" * (total // 3))

    def test_control_characters_are_passed_through(self):
        """NUL bytes, ANSI colour codes and other control characters are not
        line terminators and must reach the caller untouched."""
        line = "\x1b[31mred\x1b[0m\x00nul\x07bell\x08back"
        proc = make_proc(f"print({line!r})\n")
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, [line])

    def test_mixed_line_endings(self):
        proc = make_proc(
            "import sys\n" "sys.stdout.write('a\\nb\\r\\nc\\rd\\n\\re\\n')\n"
        )
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        # only \n splits; a leading \r stays, a trailing \r is trimmed
        self.assertEqual(out, ["a", "b", "c\rd", "\re"])

    def test_stdout_closed_early_while_stderr_keeps_going(self):
        """One pipe reaching EOF must not stop the other being drained."""
        proc = make_proc(
            "import os, sys, time\n"
            "print('last out', flush=True)\n"
            "os.close(sys.stdout.fileno())\n"
            "for i in range(5):\n"
            "    time.sleep(0.05)\n"
            "    print(f'err-{i}', file=sys.stderr, flush=True)\n"
        )
        rc, out, err = stream_process_output(
            proc, print_stdout=False, print_stderr=False, timeout=10
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, ["last out"])
        self.assertEqual(err, [f"err-{i}" for i in range(5)])

    def test_grandchild_holding_pipes_is_bounded_by_timeout(self):
        """The direct child exits but a background grandchild inherits the
        pipes, so EOF never comes. timeout must still return control."""
        proc = make_proc(
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c',"
            " 'import time; time.sleep(5)'])\n"
            "print('parent done', flush=True)\n"
        )
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=1, print_stdout=False, print_stderr=False
            )
        self.assertLess(time.monotonic() - start, 4)
        self.assertEqual(cm.exception.output, "parent done")


class TestEncodingAndBuffering(ut.TestCase):

    def _run_with_encoding(self, encoding):
        code = (
            "import sys\n"
            "for s in ('café', 'naïve'):\n"
            "    sys.stdout.buffer.write((s + '\\n').encode({!r}))\n"
        ).format(encoding)
        proc = sp.Popen(
            [sys.executable, "-c", code],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            encoding=encoding,
        )
        return stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )

    def test_respects_popen_single_byte_encoding(self):
        """Lines are decoded with the encoding configured on the Popen
        streams rather than assuming UTF-8."""
        _, out, _ = self._run_with_encoding("latin-1")
        self.assertEqual(out, ["café", "naïve"])

    def test_respects_popen_multibyte_encoding(self):
        """Newlines are found after decoding, so encodings where b'\\n' is
        not a standalone newline (UTF-16) still split correctly."""
        _, out, _ = self._run_with_encoding("utf-16-le")
        self.assertEqual(out, ["café", "naïve"])

    def test_multibyte_char_split_across_reads(self):
        """A multibyte character split across two reads must be decoded
        correctly instead of producing replacement characters."""
        proc = make_proc(
            "import sys, time\n"
            "data = 'é'.encode()\n"
            "sys.stdout.buffer.write(data[:1]); sys.stdout.flush()\n"
            "time.sleep(0.2)\n"
            "sys.stdout.buffer.write(data[1:] + b'\\n')\n"
        )
        _, out, _ = stream_process_output(
            proc, print_stdout=False, print_stderr=False
        )
        self.assertEqual(out, ["é"])

    def test_newline_free_output_is_emitted_in_bounded_chunks(self):
        """Output without any newline must not be buffered without bound;
        it is force-emitted once MAX_PENDING_CHARS is reached."""
        total = MAX_PENDING_CHARS * 3 + 10
        proc = make_proc(
            "import sys\n" "sys.stdout.write('x' * {})\n".format(total)
        )
        _, out, _ = stream_process_output(
            proc, stdout_maxlen=None, print_stdout=False, print_stderr=False
        )
        self.assertEqual("".join(out), "x" * total)
        self.assertGreater(len(out), 1)
        self.assertTrue(all(len(line) < MAX_PENDING_CHARS * 2 for line in out))


class TestTimeout(ut.TestCase):

    def assert_killed_in_time(self, proc, start, timeout):
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, timeout + 3)
        self.assertIsNotNone(proc.returncode)
        self.assertNotEqual(proc.returncode, 0)

    def test_silent_hang_is_killed(self):
        proc = make_proc(
            "import time\n" "print('started', flush=True)\n" "time.sleep(60)\n"
        )
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=0.5, print_stdout=False, print_stderr=False
            )
        self.assert_killed_in_time(proc, start, 0.5)
        self.assertEqual(cm.exception.timeout, 0.5)
        self.assertEqual(cm.exception.output, "started")

    def test_continuously_printing_process_is_killed(self):
        """Constant output keeps select() returning events, the deadline
        must still be enforced."""
        proc = make_proc(
            "import sys, time\n"
            "while True:\n"
            "    print('tick', flush=True)\n"
            "    print('tock', file=sys.stderr, flush=True)\n"
            "    time.sleep(0.01)\n"
        )
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=0.5, print_stdout=False, print_stderr=False
            )
        self.assert_killed_in_time(proc, start, 0.5)
        self.assertTrue(cm.exception.output.startswith("tick"))
        self.assertTrue(cm.exception.stderr.startswith("tock"))

    def test_partial_line_is_included_on_timeout(self):
        proc = make_proc(
            "import sys, time\n"
            "sys.stdout.write('no newline')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=0.5, print_stdout=False, print_stderr=False
            )
        self.assertEqual(cm.exception.output, "no newline")

    def test_process_closing_pipes_but_still_running_is_killed(self):
        proc = make_proc(
            "import os, sys, time\n"
            "print('bye', flush=True)\n"
            "os.close(sys.stdout.fileno())\n"
            "os.close(sys.stderr.fileno())\n"
            "time.sleep(60)\n"
        )
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=0.5, print_stdout=False, print_stderr=False
            )
        self.assert_killed_in_time(proc, start, 0.5)
        self.assertEqual(cm.exception.output, "bye")

    def test_finishing_within_timeout_returns_normally(self):
        proc = make_proc("print('done')\n")
        rc, out, err = stream_process_output(
            proc, timeout=10, print_stdout=False, print_stderr=False
        )
        self.assertEqual((rc, out, err), (0, ["done"], []))

    def test_zero_timeout_kills_immediately(self):
        proc = make_proc("import time\ntime.sleep(60)\n")
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired):
            stream_process_output(
                proc, timeout=0, print_stdout=False, print_stderr=False
            )
        self.assert_killed_in_time(proc, start, 0)

    def test_selector_is_closed_on_timeout(self):
        created = []
        real_selector_cls = selectors.DefaultSelector

        def make_selector():
            created.append(real_selector_cls())
            return created[-1]

        proc = make_proc("import time\ntime.sleep(60)\n")
        with mock.patch(
            "checkbox_support.helpers.stream_subprocess.selectors"
            ".DefaultSelector",
            side_effect=make_selector,
        ):
            with self.assertRaises(sp.TimeoutExpired):
                stream_process_output(
                    proc, timeout=0.2, print_stdout=False, print_stderr=False
                )
        # a closed selector has no map
        self.assertIsNone(created[0].get_map())

    def test_pipes_are_closed_on_timeout(self):
        proc = make_proc("import time\ntime.sleep(60)\n")
        with self.assertRaises(sp.TimeoutExpired):
            stream_process_output(
                proc, timeout=0.2, print_stdout=False, print_stderr=False
            )
        self.assertTrue(proc.stdout.closed)
        self.assertTrue(proc.stderr.closed)

    def wait_until_buffered(self, proc):
        """Block until the child has written to both pipes, without reading."""
        streams = {proc.stdout, proc.stderr}
        ready = set()
        deadline = time.monotonic() + 5
        while ready != streams and time.monotonic() < deadline:
            r, _, _ = select.select(list(streams - ready), [], [], 0.1)
            ready.update(r)
        self.assertEqual(ready, streams, "child never wrote")
        # the child writes each stream in one go, give it time to finish
        time.sleep(0.2)

    def test_output_buffered_in_pipes_is_drained_on_timeout(self):
        """Output the child already wrote must not be lost just because the
        deadline passed before we got around to reading it."""
        proc = make_proc(
            "import sys, time\n"
            "sys.stdout.write(''.join(f'out-{i}\\n' for i in range(500)))\n"
            "sys.stdout.write('partial')\n"
            "sys.stdout.flush()\n"
            "sys.stderr.write('last words before hang\\n')\n"
            "sys.stderr.flush()\n"
            "time.sleep(60)\n"
        )
        self.wait_until_buffered(proc)
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc,
                stdout_maxlen=None,
                timeout=0,
                print_stdout=False,
                print_stderr=False,
            )
        self.assertEqual(
            cm.exception.output.split("\n"),
            [f"out-{i}" for i in range(500)] + ["partial"],
        )
        self.assertEqual(cm.exception.stderr, "last words before hang")

    def test_incomplete_multibyte_char_is_flushed_on_timeout(self):
        """A grandchild keeps the pipe open, so EOF never comes; the decoder
        must still be flushed instead of silently holding the bytes."""
        proc = make_proc(
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c',"
            " 'import time; time.sleep(5)'])\n"
            "sys.stdout.buffer.write('ok '.encode() + 'é'.encode()[:1])\n"
            "sys.stdout.flush()\n"
            "sys.stderr.write('x')\n"
            "sys.stderr.flush()\n"
            "time.sleep(60)\n"
        )
        self.wait_until_buffered(proc)
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc, timeout=0, print_stdout=False, print_stderr=False
            )
        self.assertEqual(cm.exception.output, "ok \ufffd")

    def test_drain_is_bounded_when_grandchild_floods_the_pipe(self):
        """A grandchild that keeps writing must not keep us draining forever
        after the timeout."""
        proc = make_proc(
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c',"
            " 'import sys\\nwhile True: sys.stdout.write(\"x\" * 65536)'])\n"
            "import time; time.sleep(60)\n"
        )
        start = time.monotonic()
        with self.assertRaises(sp.TimeoutExpired) as cm:
            stream_process_output(
                proc,
                stdout_maxlen=None,
                timeout=0.5,
                print_stdout=False,
                print_stderr=False,
            )
        self.assertLess(time.monotonic() - start, 10)
        self.assertGreater(len(cm.exception.output), 0)


class TestResourceCleanup(ut.TestCase):

    def test_pipes_are_closed_after_normal_exit(self):
        proc = make_proc("print('x')\n")
        stream_process_output(proc, print_stdout=False, print_stderr=False)
        self.assertTrue(proc.stdout.closed)
        self.assertTrue(proc.stderr.closed)


if __name__ == "__main__":
    ut.main()
