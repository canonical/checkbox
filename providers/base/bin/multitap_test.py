#!/usr/bin/env python3
# Copyright 2018 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

"""
Run `xinput test-xi2` and monitor it for multifinger tap on a touchscreen.
"""

import re
import subprocess
import sys

EVENT_HEADER_RE = re.compile(r'^EVENT type (\d+) \((\w+)\)')


class Xi2Parser:
    def __init__(self):
        self._current_payload = ''
        self._current_event = ()
        self._callbacks = dict()

    def register_callback(self, event_type, fn):
        self._callbacks[event_type] = fn

    def parse_line(self, line):
        if line.startswith(' '):
            self._current_payload += line
        else:
            matches = EVENT_HEADER_RE.match(line)
            if not matches:
                return
            if self._current_event:
                self._emit_event()
            self._current_event = (matches.groups())

    def eof(self):
        if self._current_event:
            self._emit_event()

    def _emit_event(self):
        event_data = dict()
        for line in self._current_payload.split('\n'):
            if ':' in line:
                k, v = line.strip().split(':', 1)
                event_data[k] = v
        cb = self._callbacks.get(self._current_event[1])
        if cb:
            cb(event_data)
        self._current_payload = ''
        self._current_event = ()


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isnumeric():
        raise SystemExit('Usage {} FINGER_COUNT'.format(sys.argv[0]))
    print('Waiting for {}-finger tap'.format(sys.argv[1]))

    parser = Xi2Parser()
    fingers = 0

    def begin(ev):
        nonlocal fingers
        fingers += 1
        if fingers == int(sys.argv[1]):
            print('SUCCESS! {}-finger tap detected!'.format(sys.argv[1]))
            raise SystemExit(0)

    def end(ev):
        nonlocal fingers
        fingers -= 1
        if fingers < 0:
            # it may happen if the program started with finger already touching
            fingers = 0

    parser.register_callback('TouchBegin', begin)
    parser.register_callback('TouchEnd', end)
    proc = subprocess.Popen(
        ['xinput', 'test-xi2', '--root'], stdout=subprocess.PIPE)
    while not proc.stdout.closed:
        line = proc.stdout.readline().decode(sys.stdout.encoding)
        if not line:
            break
        parser.parse_line(line)
    parser.eof()


if __name__ == '__main__':
    main()
