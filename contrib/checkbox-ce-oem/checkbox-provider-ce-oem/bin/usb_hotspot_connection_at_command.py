#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>
"""WWAN-as-USB-hotspot connection test driven by a JSON config.

Targets a WWAN module attached as a USB cdc-acm device, used purely to
bring up a data connection ("USB hotspot" style) rather than a full
ModemManager-integrated modem. The JSON config for a device has two,
independently-optional parts:

  {
    "<MODULE_NAME>": {
      "setup": ["<shell command>", ...],
      "connect": {"<step name>": "<AT command>" | {spec}, ...}
    }
  }

- "setup": plain shell commands (e.g. modprobe/rfkill/ip) run in order
  to bring the module up. Execution stops at the first failure.
- "connect": AT commands sent over the module's serial control
  interface (WWAN_CONTROL_IF) to make the data connection. Execution
  stops at the first failing step.

Both parts may be omitted/empty, and the whole config is optional: with
nothing configured, the script just pings over WWAN_NET_IF. Any
provided setup or connect command that fails causes the script to exit
1.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time

import serial

PLAINBOX_PROVIDER_DATA = os.getenv("PLAINBOX_PROVIDER_DATA", "")
WWAN_AT_COMMAND_DATA_DIR = os.path.join(
    PLAINBOX_PROVIDER_DATA, "wwan_at_command"
)

# Terminator lines that end an AT command's response.
AT_OK = "OK"
AT_ERROR_PREFIXES = ("ERROR", "+CME ERROR", "+CMS ERROR")


def resolve_config_path(wwan_at_command):
    """Resolve a WWAN_AT_COMMAND_JSON value to a config file path.

    If `wwan_at_command` is already a full path (absolute, or contains
    a path separator), it is used as-is. Otherwise it's treated as a
    bare filename and looked up inside
    $PLAINBOX_PROVIDER_DATA/wwan_at_command/. A config is entirely
    optional: when WWAN_AT_COMMAND_JSON isn't set (and --config isn't
    passed), the script just pings over WWAN_NET_IF.
    """
    if os.path.isabs(wwan_at_command) or os.sep in wwan_at_command:
        return wwan_at_command
    return os.path.join(WWAN_AT_COMMAND_DATA_DIR, wwan_at_command)


DEFAULT_CONFIG = (
    resolve_config_path(os.environ["WWAN_AT_COMMAND_JSON"])
    if os.environ.get("WWAN_AT_COMMAND_JSON")
    else None
)


def run_cmd(args):
    """Run a command; return (returncode, stdout, stderr)."""
    cmd_str = " ".join(args)
    logging.info("[CMD] %s", cmd_str)
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, stdout, stderr


def parse_at_response(raw_text):
    """Extract the meaningful response text from an AT command's output.

    Strips the terminator line (OK/ERROR/+CME ERROR/+CMS ERROR) and any
    blank lines, returning what's left joined back together (usually a
    single '+CMD: ...' style line, or empty for a bare OK).
    """
    lines = [
        line
        for line in raw_text.splitlines()
        if line and line != AT_OK and not line.startswith(AT_ERROR_PREFIXES)
    ]
    return "\n".join(lines)


REGISTRATION_STATES = {
    "0": "not-registered",
    "1": "home",
    "2": "searching",
    "3": "denied",
    "4": "unknown",
    "5": "roaming",
}


class ModemAtController:
    """Wraps the WWAN module's AT-command control interface (serial port).

    Owns the serial connection to the modem and every operation that
    talks to it directly (module detection, radio enable,
    registration/operator queries, connection setup, reset/recovery),
    instead of threading a raw serial.Serial object through a long
    list of ser-taking functions. Keeping this state and behaviour
    together in one class makes it easier to extend later (e.g.
    module-specific quirks, a different transport, or reusing the same
    modem across multiple test actions).
    """

    def __init__(self, device, baudrate=115200, timeout=2):
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def open(self, handshake_attempts=3, handshake_retry_wait=1):
        """Open the control interface and disable command echo (ATE0).

        The modem's AT command parser isn't always ready the instant
        its control interface device node appears (common right after
        boot or a USB replug), so the very first command can be lost.
        Retry the ATE0 handshake a few times before giving up, rather
        than silently continuing with echo still enabled/unconfirmed.
        """
        logging.info("[SERIAL] Opening control interface %s ...", self.device)
        self.ser = serial.Serial(
            self.device, baudrate=self.baudrate, timeout=self.timeout
        )
        self.ser.reset_input_buffer()
        for attempt in range(1, handshake_attempts + 1):
            rc, raw = self.send_command("ATE0", timeout=2)
            if rc == 0:
                return self
            logging.warning(
                "[SERIAL] ATE0 handshake attempt %d/%d failed (%s), "
                "modem may not be ready yet ...",
                attempt,
                handshake_attempts,
                raw.strip() or "no response",
            )
            if attempt < handshake_attempts:
                time.sleep(handshake_retry_wait)
        logging.error(
            "[SERIAL] ATE0 handshake never succeeded on %s after %d "
            "attempts; continuing anyway, but subsequent AT commands "
            "may fail",
            self.device,
            handshake_attempts,
        )
        return self

    def open_polling(self, timeout, interval=3):
        """Poll for the control interface to (re)appear for up to timeout s.

        Used after AT+CRESET, which physically resets the modem and
        causes real USB re-enumeration, so the device node can briefly
        disappear before coming back. Returns self once open, or None
        on timeout.
        """
        deadline = time.time() + timeout
        while True:
            try:
                return self.open()
            except (serial.SerialException, OSError) as exc:
                logging.info(
                    "[SERIAL] %s not ready yet (%s), retrying ...",
                    self.device,
                    exc,
                )
            if time.time() >= deadline:
                return None
            time.sleep(interval)

    def close(self):
        """Close the control interface, if currently open."""
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def send_command(self, cmd, timeout=10):
        """Send a raw AT command; return (rc, raw_response_text).

        rc == 0 if the response ended with 'OK', rc == 1 if it ended
        with 'ERROR'/'+CME ERROR'/'+CMS ERROR', or on timeout without
        either.
        """
        logging.info("[AT] -> %s", cmd)
        self.ser.reset_input_buffer()
        payload = "{}\r\n".format(cmd).encode("ascii", errors="replace")
        self.ser.write(payload)
        self.ser.flush()

        lines = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw_line = self.ser.readline()
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line == cmd:
                continue
            lines.append(line)
            if line == AT_OK:
                return 0, "\n".join(lines)
            if line.startswith(AT_ERROR_PREFIXES):
                return 1, "\n".join(lines)
        return 1, "\n".join(lines)

    def query(self, cmd, timeout=10):
        """Send an AT command and return its parsed response, or None."""
        rc, raw = self.send_command(cmd, timeout=timeout)
        if rc != 0:
            return None
        return parse_at_response(raw)

    def run_at_step(self, name, spec, env, timeout=15):
        """Execute one AT-command step; return True on pass.

        `spec` is either a plain AT command string (pass = any
        response came back), or a dict {"cmd": <AT command>, ...} for
        steps that need to validate the actual value, not just
        presence of a response:
          - "expect": <substring> the response must contain
          - "expect_nonempty": True if the response must be non-empty
          - "expect_min": <int> the first number in the response must
            be >=
          - "poll": True to retry for up to WWAN_SETUPTIME seconds
            instead of failing immediately (e.g. GPRS attach / PDP
            context / IP assignment can take a few seconds after
            auto-dial is set)
        """
        if isinstance(spec, dict):
            cmd = spec["cmd"]
            expect = spec.get("expect")
            expect_nonempty = spec.get("expect_nonempty", False)
            expect_min = spec.get("expect_min")
            poll = spec.get("poll", False)
        else:
            cmd, expect, expect_nonempty, expect_min, poll = (
                spec,
                None,
                False,
                None,
                False,
            )

        cmd = cmd.replace("{APN}", env["WWAN_APN"])

        deadline = time.time() + int(os.environ.get("WWAN_SETUPTIME", "30"))
        interval = 3
        while True:
            logging.info("[AT] %s -> %s", name, cmd)
            rc, raw = self.send_command(cmd, timeout=timeout)
            resp = parse_at_response(raw)
            logging.info("[AT] rc=%s response=%s", rc, raw.strip())

            if expect is not None:
                passed = rc == 0 and expect in resp
            elif expect_nonempty:
                passed = rc == 0 and bool(resp)
            elif expect_min is not None:
                num_m = re.search(r"-?\d+", resp) if resp else None
                passed = (
                    rc == 0
                    and num_m is not None
                    and int(num_m.group()) >= expect_min
                )
            else:
                passed = rc == 0

            if passed or not poll or time.time() >= deadline:
                break
            time.sleep(interval)

        if passed:
            logging.info("[PASS] %s", name)
        else:
            logging.error("[FAIL] %s: rc=%s resp=%s", name, rc, repr(resp))
        return passed

    def run_connect_steps(self, connect_steps, env):
        """Run all "connect" AT steps in order; return True if all pass.

        connect_steps is a dict of {step_name: at_command_or_spec}.
        Stops at the first failing step.
        """
        for name, spec in connect_steps.items():
            if not self.run_at_step(name, spec, env):
                logging.error("Aborting: AT command '%s' failed", name)
                return False
        return True

    def send_reset(self):
        """Send AT+CRESET; return True if the modem accepted the command."""
        logging.info("[RESET] Sending AT+CRESET ...")
        rc, raw = self.send_command("AT+CRESET", timeout=10)
        logging.info("[RESET] rc=%s response=%s", rc, raw.strip())
        if rc != 0:
            logging.error("[FAIL] AT+CRESET failed")
            return False
        logging.info("[PASS] AT+CRESET accepted")
        return True

    def verify_cops(self, timeout):
        """Verify AT+COPS? responds within `timeout` seconds."""
        logging.info(
            "[RESET] Verifying AT+COPS? responds within %ss ...", timeout
        )
        rc, raw = self.send_command("AT+COPS?", timeout=timeout)
        logging.info("[RESET] AT+COPS? rc=%s response=%s", rc, raw.strip())
        return rc == 0

    def radio_cycle(self, wait_seconds):
        """Cycle the radio (CFUN=4 then 1) to nudge stuck registration."""
        logging.info("[RESET] Cycling radio: AT+CFUN=4 -> AT+CFUN=1 ...")
        self.send_command("AT+CFUN=4", timeout=10)
        time.sleep(3)
        self.send_command("AT+CFUN=1", timeout=10)
        logging.info(
            "[RESET] Waiting %ss for the radio to come back up ...",
            wait_seconds,
        )
        time.sleep(wait_seconds)

    def get_registration(self):
        """Return the 3GPP registration state (e.g. 'home', 'roaming')."""
        resp = self.query("AT+CREG?")
        if not resp:
            return None
        m = re.search(r"\+CREG:\s*\d+,\s*(\d+)", resp)
        if not m:
            return None
        return REGISTRATION_STATES.get(m.group(1), m.group(1))

    def get_operator_id(self):
        """Return the numeric PLMN operator id, requesting numeric fmt."""
        self.send_command("AT+COPS=3,2", timeout=5)
        resp = self.query("AT+COPS?")
        if not resp:
            return None
        m = re.search(r'\+COPS:\s*\d+,\d+,"?(\d+)"?', resp)
        return m.group(1) if m else None

    def wait_for_registration(self, timeout, radio_cycle_wait, interval=5):
        """Poll registration state; do one radio cycle if it stays denied.

        Returns (passed, registration, operator_id).
        """
        deadline = time.time() + timeout
        cycled = False
        registration = operator_id = None
        while True:
            registration = self.get_registration()
            operator_id = self.get_operator_id()
            logging.info(
                "[RESET] registration=%s operator_id=%s",
                registration,
                operator_id,
            )
            if registration in ("home", "roaming"):
                return True, registration, operator_id
            if time.time() >= deadline:
                if not cycled:
                    cycled = True
                    self.radio_cycle(radio_cycle_wait)
                    deadline = time.time() + timeout
                    continue
                return False, registration, operator_id
            time.sleep(interval)


def deprioritize_default_route(iface, metric=200):
    """Raise the metric of the default route DHCP installed on iface.

    A DHCP lease on the WWAN interface can install a default route that
    outranks the DUT's management interface (e.g. a lower metric than
    the control network), hijacking all default-routed traffic. Since
    this test always targets iface explicitly (ping -I), it doesn't
    need to win the global default route race, so push its metric up
    to keep the management route preferred.
    """
    _, stdout, _ = run_cmd(["ip", "route", "show", "default", "dev", iface])
    line = stdout.strip().splitlines()[0] if stdout.strip() else ""
    m = re.search(r"via\s+(\S+)", line)
    if not m:
        logging.info(
            "[NET] No default route via %s found to deprioritize", iface
        )
        return
    gw = m.group(1)
    logging.info(
        "[NET] Lowering priority of default route via %s dev %s"
        " (metric=%d)",
        gw,
        iface,
        metric,
    )
    run_cmd(
        [
            "ip",
            "route",
            "replace",
            "default",
            "via",
            gw,
            "dev",
            iface,
            "metric",
            str(metric),
        ]
    )


def log_connection_diagnostics(iface, modem=None):
    """Log modem/network state to help debug a failed IP acquisition.

    `modem` is optional: when the config had no "connect" AT steps, no
    serial control interface is opened, so only the OS-level (ip/dmesg)
    diagnostics are available.
    """
    logging.info("[DIAG] ---- connection diagnostics ----")
    if modem is not None:
        for cmd in (
            "AT+CGATT?",
            "AT+CGACT?",
            "AT+CGDCONT?",
            "AT+CGPADDR=1",
        ):
            resp = modem.query(cmd)
            logging.info("[DIAG] %s -> %s", cmd, resp)

    _, link_stdout, _ = run_cmd(["ip", "-s", "link", "show", "dev", iface])
    logging.info(
        "[DIAG] ip -s link show dev %s:\n%s", iface, link_stdout.strip()
    )

    _, dmesg_stdout, _ = run_cmd(["sh", "-c", "dmesg | tail -n 40"])
    logging.info("[DIAG] dmesg (tail):\n%s", dmesg_stdout.strip())
    logging.info("[DIAG] ---------------------------------")


def run_ping(iface, modem=None):
    """Bring up iface, wait for a DHCP lease, then ping 8.8.8.8.

    The DUT's own network manager (NetworkManager, per the boards'
    provisioning config) already auto-configures new interfaces via
    DHCP; a reboot alone brings the IP back, confirming NetworkManager
    (not this script) owns the lease. So this does not run its own
    DHCP client or flush the address (which was tearing down NM's
    state without it recovering on its own); it only nudges
    NetworkManager to (re)connect the device and waits for the lease.

    `modem` is optional and only used to enrich diagnostics on failure
    (see log_connection_diagnostics).
    """
    # 1. Bring the link UP
    logging.info("[NET] Bringing up interface %s ...", iface)
    rc, _, stderr = run_cmd(["ip", "link", "set", iface, "up"])
    if rc != 0:
        logging.error(
            "[NET] Failed to bring up %s: rc=%s stderr=%s",
            iface,
            rc,
            stderr.strip(),
        )
        return False

    # 2. Ask NetworkManager to (re)connect the device; best-effort only,
    #    NetworkManager may already be handling this on its own.
    logging.info("[NET] Asking NetworkManager to connect %s ...", iface)
    run_cmd(["nmcli", "device", "connect", iface])

    # 3. Wait for NetworkManager's own DHCP client to assign a lease
    setuptime = int(os.environ.get("WWAN_SETUPTIME", "30"))
    logging.info(
        "[NET] Waiting up to %ss for a DHCP lease on %s ...",
        setuptime,
        iface,
    )
    ip_stdout = ""
    waited = 0
    interval = 2
    while waited <= setuptime:
        _, ip_stdout, _ = run_cmd(["ip", "addr", "show", "dev", iface])
        if re.search(r"inet\s+\d+\.\d+\.\d+\.\d+", ip_stdout):
            break
        time.sleep(interval)
        waited += interval
    logging.info("[NET] ip addr show dev %s:\n%s", iface, ip_stdout.strip())

    if not re.search(r"inet\s+\d+\.\d+\.\d+\.\d+", ip_stdout):
        logging.error(
            "[NET] No IP assigned on %s after waiting %ss", iface, setuptime
        )
        log_connection_diagnostics(iface, modem)
        return False

    # 3b. Don't let the WWAN default route hijack the system's routing
    deprioritize_default_route(iface)

    # 5. Ping
    logging.info("[PING] Ping 8.8.8.8 via %s", iface)
    rc, stdout, stderr = run_cmd(
        ["ping", "-I", iface, "-c", "4", "-W", "5", "8.8.8.8"]
    )
    logging.info("[PING] rc=%s", rc)
    logging.info("[PING] stdout:\n%s", stdout.strip())
    if stderr.strip():
        logging.warning("[PING] stderr:\n%s", stderr.strip())

    m_rx = re.search(r"(\d+) received", stdout)
    received = int(m_rx.group(1)) if m_rx else 0
    passed = rc == 0 and received == 4
    if passed:
        logging.info("[PASS] Ping 8.8.8.8")
    else:
        logging.error("[FAIL] Ping 8.8.8.8: %s/4 packets received", received)
    return passed


def reset_and_recover(device):
    """Run the reset/recovery procedure; return True on success.

    Issues AT+CRESET, waits for the control interface to reappear
    (AT+CRESET causes real USB re-enumeration, so the device node can
    briefly disappear), verifies AT+COPS? responds, then waits for
    network registration, falling back to one AT+CFUN radio cycle if
    registration stays denied for too long.

    Not every module/project needs this (see the
    has_wwan_module_via_at_command_reset_recovery manifest entry gating
    the job that calls this), and it needs much longer timeouts than
    the normal connection test, so it's driven by its own WWAN_RESET_*
    environment variables rather than WWAN_SETUPTIME.
    """
    reset_wait = int(os.environ.get("WWAN_RESET_WAIT", "30"))
    cops_timeout = int(os.environ.get("WWAN_RESET_COPS_TIMEOUT", "30"))
    denied_timeout = int(os.environ.get("WWAN_RESET_DENIED_TIMEOUT", "120"))
    radio_cycle_wait = int(os.environ.get("WWAN_RESET_RADIO_CYCLE_WAIT", "45"))

    logging.info("=== WWAN Reset & Recovery Test ===")
    modem = ModemAtController(device)
    modem.open()
    try:
        if not modem.send_reset():
            return False
    finally:
        modem.close()

    logging.info(
        "[RESET] Waiting up to %ss for %s to reappear ...",
        reset_wait,
        device,
    )
    if modem.open_polling(timeout=reset_wait) is None:
        logging.error(
            "[FAIL] %s did not reappear within %ss", device, reset_wait
        )
        return False
    logging.info("[PASS] %s reappeared", device)

    try:
        if not modem.verify_cops(cops_timeout):
            logging.error(
                "[FAIL] AT+COPS? did not respond within %ss after reset",
                cops_timeout,
            )
            return False
        logging.info("[PASS] AT+COPS? responded after reset")

        ok, registration, operator_id = modem.wait_for_registration(
            denied_timeout, radio_cycle_wait
        )
        if not ok:
            logging.error(
                "[FAIL] Modem did not re-register (registration=%s) within"
                " the allotted time, even after a radio cycle",
                registration,
            )
            return False

        logging.info(
            "[PASS] Modem re-registered: registration=%s operator_id=%s",
            registration,
            operator_id,
        )
        return True
    finally:
        modem.close()


def load_config(path):
    """Load and return the JSON config, or {} if no path/file is given.

    A config is entirely optional: no path, or a path to a file that
    doesn't exist, both mean "nothing configured" (ping-only mode) so
    that a device with no setup/connect needs can simply omit
    WWAN_AT_COMMAND_JSON rather than pointing at an empty JSON file.
    """
    if not path or not os.path.isfile(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def extract_module_block(config):
    """Return (module_name, block) for the sole top-level entry.

    The config is expected to have exactly one top-level key (the
    module name, used only for logging) wrapping the "setup" and
    "connect" parts. An empty config yields (None, {}), which callers
    treat as "nothing to do but ping".
    """
    if not config:
        return None, {}
    if len(config) > 1:
        logging.warning(
            "Config defines %d modules (%s); only the first is used",
            len(config),
            ", ".join(config.keys()),
        )
    name = next(iter(config))
    return name, config[name] or {}


def run_setup_commands(setup_cmds):
    """Run each "setup" shell command in order; return True if all pass.

    Each entry is a full shell command line (may use pipes/redirection
    etc.), so it's run through the shell -- the same trust level as a
    job's own `command:` field, since these come from static local
    test-config JSON files maintained by the test author, not
    external/runtime input. Stops at the first failing command.
    """
    for cmd in setup_cmds:
        logging.info("[SETUP] %s", cmd)
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if stdout.strip():
            logging.info("[SETUP] stdout:\n%s", stdout.strip())
        if stderr.strip():
            logging.info("[SETUP] stderr:\n%s", stderr.strip())
        if proc.returncode != 0:
            logging.error(
                "[FAIL] Setup command failed (rc=%s): %s",
                proc.returncode,
                cmd,
            )
            return False
        logging.info("[PASS] %s", cmd)
    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description="WWAN-as-USB-hotspot connection test"
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to the JSON config (default: taken from the"
        " WWAN_AT_COMMAND_JSON environment variable; a bare filename"
        " is resolved against $PLAINBOX_PROVIDER_DATA/wwan_at_command/,"
        " a full path is used as-is). Optional: with no config (or an"
        " empty one), the script just pings over WWAN_NET_IF",
    )
    parser.add_argument(
        "--action",
        choices=("connect", "reset-recovery"),
        default="connect",
        help="'connect' (default) runs the setup/connect/ping test;"
        " 'reset-recovery' issues AT+CRESET and verifies the modem"
        " recovers and re-registers afterwards",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args = parse_args()

    control_if = os.environ.get("WWAN_CONTROL_IF", "")

    if args.action == "reset-recovery":
        if not control_if:
            logging.error("Environment variable WWAN_CONTROL_IF is not set")
            sys.exit(1)
        sys.exit(0 if reset_and_recover(control_if) else 1)

    iface = os.environ.get("WWAN_NET_IF", "")
    if not iface:
        logging.error("Environment variable WWAN_NET_IF is not set")
        sys.exit(1)

    config = load_config(args.config)
    module_name, block = extract_module_block(config)
    setup_cmds = list(block.get("setup") or [])
    connect_steps = block.get("connect") or {}

    logging.info("=== WWAN USB-Hotspot Connection Test ===")
    logging.info("Module      : %s", module_name or "(none configured)")
    logging.info("Interface   : %s", iface)

    if setup_cmds and not run_setup_commands(setup_cmds):
        sys.exit(1)

    modem = None
    if connect_steps:
        if not control_if:
            logging.error("Environment variable WWAN_CONTROL_IF is not set")
            sys.exit(1)
        apn = os.environ.get("WWAN_APN", "")
        if not apn:
            logging.error("Environment variable WWAN_APN is not set")
            sys.exit(1)
        env = {"WWAN_APN": apn, "WWAN_NET_IF": iface}

        modem = ModemAtController(control_if)
        modem.open()
        if not modem.run_connect_steps(connect_steps, env):
            modem.close()
            sys.exit(1)

    try:
        ping_ok = run_ping(iface, modem)
    finally:
        if modem is not None:
            modem.close()

    sys.exit(0 if ping_ok else 1)


if __name__ == "__main__":
    main()
