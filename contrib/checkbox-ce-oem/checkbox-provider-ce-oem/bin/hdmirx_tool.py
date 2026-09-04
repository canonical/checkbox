#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
"""CLI entry point for the pure-Python HDMI RX (input) test.

This is the only script the checkbox jobs invoke. It selects a
platform backend (auto-detect or ``--backend``) and runs one
self-verifying sub-command per job. Exit status is 0 on pass and 1
on failure; ``--json`` prints a machine-readable result.
"""

import argparse
import json
import sys
import time

from hdmirx_utils import (
    AbiMismatch,
    verify_audio,
    verify_events,
    verify_video,
)
from hdmirx_generic import V4L2Backend
from hdmirx_genio import GenioIoctlBackend

# Registry order: prefer the platform-specific ioctl backend, then the
# generic mainline V4L2 one.
BACKENDS = [GenioIoctlBackend, V4L2Backend]


class NoBackendError(RuntimeError):
    """No HDMI RX backend is available on this system."""


def detect(preferred=None):
    """Return an available backend instance.

    ``preferred`` selects a backend by ``name`` and forces it even if it
    does not detect itself. An empty string (e.g. an unset
    ``HDMIRX_BACKEND``) is a hard error, not a silent auto-detect.
    ``None`` auto-detects the first available backend. Raises
    ``NoBackendError`` on an empty, unknown, or absent backend.
    """
    known = ", ".join(c.name for c in BACKENDS)
    if preferred is not None:
        if not preferred.strip():
            raise NoBackendError(
                "no backend selected: set HDMIRX_BACKEND to one of: "
                "{}".format(known)
            )
        for cls in BACKENDS:
            if cls.name == preferred:
                return cls()
        raise NoBackendError(
            "unknown backend {!r}; known: {}".format(preferred, known)
        )
    for cls in BACKENDS:
        backend = cls()
        if backend.is_available():
            return backend
    raise NoBackendError(
        "no HDMI RX backend available (tried: {})".format(known)
    )


def _poll_until(predicate, timeout=5.0, interval=0.5):
    """Poll ``predicate`` until true or ``timeout`` (seconds) elapses."""
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def _cmd_module_check(backend, args):
    if backend.module_present():
        return [], {"module_present": True}
    return ["HDMI RX kernel driver is not loaded"], {"module_present": False}


def _cmd_device_info(backend, args):
    info = backend.get_device_info()
    return [], info._asdict()


def _cmd_cable(backend, args):
    info = backend.get_device_info()
    data = {
        "connected": info.connected,
        "state": "hdmi connected" if info.connected else "hdmi disconnected",
    }
    if info.connected:
        return [], data
    return ["HDMI RX cable not connected (hpd/5v low)"], data


def _cmd_video_info(backend, args):
    info = backend.get_video_info()
    data = info._asdict()
    if None in (args.rh, args.rv, args.rr):
        return [], data
    return verify_video(info, args.rh, args.rv, args.rr), data


def _cmd_audio_info(backend, args):
    info = backend.get_audio_info()
    data = info._asdict()
    if None in (args.ab, args.ac, args.asf):
        return [], data
    return verify_audio(info, args.ab, args.ac, args.asf), data


def _cmd_enable(backend, args):
    backend.set_enabled(True)
    return [], {"enabled": True}


def _cmd_disable(backend, args):
    backend.set_enabled(False)
    return [], {"enabled": False}


def _cmd_disable_then_enable(backend, args):
    reasons = []
    backend.set_enabled(False)
    disconnected = _poll_until(
        lambda: not backend.get_device_info().connected, args.timeout
    )
    if not disconnected:
        reasons.append("cable still reported connected after disable")
    backend.set_enabled(True)
    reconnected = _poll_until(
        lambda: backend.get_device_info().connected, args.timeout
    )
    if not reconnected:
        reasons.append("cable not reported connected after re-enable")
    return reasons, {
        "disconnected_after_disable": disconnected,
        "reconnected_after_enable": reconnected,
    }


def _cmd_wait_event(backend, args):
    got = backend.wait_for_events(args.kind, args.timeout)
    data = {"observed": sorted(e.value for e in got)}
    return verify_events(got, args.kind, args.with_zapper), data


def _cmd_abi_selfcheck(backend, args):
    selfcheck = getattr(backend, "abi_selfcheck", None)
    if selfcheck is None:
        return [], {"skipped": "backend has no fixed ABI"}
    try:
        selfcheck()
    except AbiMismatch as exc:
        return [str(exc)], {"ok": False}
    return [], {"ok": True}


HANDLERS = {
    "module-check": _cmd_module_check,
    "device-info": _cmd_device_info,
    "cable": _cmd_cable,
    "video-info": _cmd_video_info,
    "audio-info": _cmd_audio_info,
    "enable": _cmd_enable,
    "disable": _cmd_disable,
    "disable-then-enable": _cmd_disable_then_enable,
    "wait-event": _cmd_wait_event,
    "abi-selfcheck": _cmd_abi_selfcheck,
}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Pure-Python HDMI RX (input) test tool."
    )
    parser.add_argument(
        "--backend",
        help="backend name (e.g. genio, v4l2); an empty value errors, "
        "omit to auto-detect",
    )
    parser.add_argument(
        "--json", action="store_true", help="print a JSON result"
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    for name in (
        "module-check",
        "device-info",
        "cable",
        "enable",
        "disable",
        "abi-selfcheck",
    ):
        sub.add_parser(name)

    p_video = sub.add_parser("video-info")
    p_video.add_argument("-rh", type=int, dest="rh", help="expected width")
    p_video.add_argument("-rv", type=int, dest="rv", help="expected height")
    p_video.add_argument("-rr", type=int, dest="rr", help="expected rate")

    p_audio = sub.add_parser("audio-info")
    p_audio.add_argument("-ab", type=int, dest="ab", help="expected bits")
    p_audio.add_argument("-ac", type=int, dest="ac", help="expected chans")
    p_audio.add_argument("-asf", type=float, dest="asf", help="expected kHz")

    p_dte = sub.add_parser("disable-then-enable")
    p_dte.add_argument("--timeout", type=float, default=5.0)

    p_evt = sub.add_parser("wait-event")
    p_evt.add_argument("kind", choices=["plug", "unplug"])
    p_evt.add_argument("--timeout", type=float, default=15.0)
    p_evt.add_argument("--with-zapper", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        backend = detect(args.backend)
    except NoBackendError as exc:
        _report(args, "detect", ["{}".format(exc)], {}, backend_name="none")
        return 1

    try:
        reasons, data = HANDLERS[args.command](backend, args)
    except NotImplementedError as exc:
        reasons, data = ["not supported on this backend: {}".format(exc)], {}
    except (OSError, ValueError) as exc:
        reasons, data = ["{}: {}".format(type(exc).__name__, exc)], {}

    _report(args, args.command, reasons, data, backend.name)
    return 0 if not reasons else 1


def _report(args, command, reasons, data, backend_name):
    passed = not reasons
    if args.json:
        print(
            json.dumps(
                {
                    "backend": backend_name,
                    "command": command,
                    "passed": passed,
                    "reasons": reasons,
                    "data": data,
                },
                sort_keys=True,
            )
        )
        return
    print("backend: {}".format(backend_name))
    for key, value in sorted(data.items()):
        print("  {} = {}".format(key, value))
    if passed:
        print("PASS")
    else:
        for reason in reasons:
            print("FAIL: {}".format(reason))


if __name__ == "__main__":
    sys.exit(main())
