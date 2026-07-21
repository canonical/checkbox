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
"""WWAN module connection test driven by wwan_at_command.json config."""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time

PLAINBOX_PROVIDER_DATA = os.getenv("PLAINBOX_PROVIDER_DATA", "")
WWAN_AT_COMMAND_DATA_DIR = os.path.join(
    PLAINBOX_PROVIDER_DATA, "wwan_at_command"
)


def resolve_config_path(wwan_at_command):
    """Resolve a WWAN_AT_COMMAND_JSON value to a config file path.

    If `wwan_at_command` is already a full path (absolute, or contains
    a path separator), it is used as-is. Otherwise it's treated as a
    bare filename and looked up inside
    $PLAINBOX_PROVIDER_DATA/wwan_at_command/.
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


def mmcli_list():
    """Return (rc, stdout) for mmcli -L."""
    rc, stdout, _ = run_cmd(["sudo", "mmcli", "-L"])
    return rc, stdout


def mmcli_modem_ids():
    """Return the list of ModemManager numeric indices from mmcli -L."""
    rc, stdout = mmcli_list()
    if rc != 0:
        logging.error("mmcli -L failed (rc=%s)", rc)
        sys.exit(1)
    return [
        int(m.group(1))
        for m in re.finditer(
            r"/org/freedesktop/ModemManager1/Modem/(\d+)", stdout
        )
    ]


def get_field(mm_id, key):
    """Return the value of a `key:` field from mmcli -m <mm_id> output."""
    rc, stdout, _ = run_cmd(["sudo", "mmcli", "-m", str(mm_id)])
    if rc != 0:
        return None
    for line in stdout.splitlines():
        _, _, right = line.rpartition("|")
        field, sep, value = right.strip().partition(":")
        if sep and field.strip() == key:
            return value.strip().strip("'")
    return None


def get_equipment_id(mm_id):
    """Return the equipment id (IMEI) reported by mmcli -m <mm_id>."""
    rc, stdout, _ = run_cmd(["sudo", "mmcli", "-m", str(mm_id)])
    if rc != 0:
        return None
    m = re.search(r"equipment id:\s*'?([^'\s]+)", stdout)
    return m.group(1) if m else None


def resolve_modem_index(hw_id):
    """Resolve the ModemManager numeric index for an equipment id (IMEI)."""
    for mm_id in mmcli_modem_ids():
        if get_equipment_id(mm_id) == hw_id:
            return mm_id
    logging.error("No modem found matching equipment id '%s'", hw_id)
    sys.exit(1)


def resolve_modem_index_polling(hw_id, timeout, interval=3):
    """Poll for the ModemManager index of hw_id for up to `timeout`s.

    Unlike resolve_modem_index(), this does not exit on failure; it
    returns None. Used after a modem reset, where the device
    re-enumerates over USB and may take a while to reappear (and may
    come back with a different numeric index).
    """
    deadline = time.time() + timeout
    while True:
        for mm_id in mmcli_modem_ids():
            if get_equipment_id(mm_id) == hw_id:
                return mm_id
        if time.time() >= deadline:
            return None
        time.sleep(interval)


def get_modem_state(mm_id):
    """Return the modem's ModemManager state (e.g. 'enabled', 'disabled')."""
    rc, stdout, _ = run_cmd(["sudo", "mmcli", "-m", str(mm_id)])
    if rc != 0:
        return None
    for line in stdout.splitlines():
        _, _, right = line.rpartition("|")
        key, sep, value = right.strip().partition(":")
        if sep and key.strip() == "state":
            return value.strip().strip("'")
    return None


def ensure_modem_enabled(mm_id):
    """Make sure the modem is enabled via ModemManager before testing.

    Returns True if the modem ends up in an enabled (or better) state,
    False otherwise. Never aborts the test: raw AT commands can still
    work over the primary port even while the modem stays disabled.
    """
    ready_states = (
        "enabled",
        "searching",
        "registered",
        "connecting",
        "connected",
    )
    state = get_modem_state(mm_id)
    logging.info("Modem state : %s", state)
    if state in ready_states:
        return True

    logging.info("Modem is '%s', enabling via ModemManager ...", state)
    rc, stdout, stderr = run_cmd(["sudo", "mmcli", "-m", str(mm_id), "-e"])
    if rc != 0:
        logging.warning(
            "Failed to enable modem (rc=%s): %s",
            rc,
            stderr.strip() or stdout.strip(),
        )
        return False

    state = get_modem_state(mm_id)
    logging.info("Modem state after enable: %s", state)
    if state not in ready_states:
        logging.warning(
            "Modem still not enabled (state=%s); continuing anyway",
            state,
        )
        return False
    return True


def mmcli_at(modem_idx, at_cmd, timeout=10):
    """Send an AT command via mmcli; return (rc, stdout, stderr)."""
    return run_cmd(
        [
            "sudo",
            "mmcli",
            "-m",
            str(modem_idx),
            "--command={}".format(at_cmd),
            "--timeout={}".format(timeout),
        ]
    )


def parse_response(output):
    """Extract the response value from mmcli --command output."""
    m = re.search(r"response: '([^']*)'", output)
    return m.group(1) if m else None


def run_at_query(modem_idx, at_cmd, timeout=10):
    """Send a read-only AT command and return its raw response string."""
    rc, stdout, stderr = mmcli_at(modem_idx, at_cmd, timeout=timeout)
    resp = parse_response(stdout)
    if rc != 0 or resp is None:
        logging.warning(
            "[DIAG] %s -> rc=%s stdout=%s stderr=%s",
            at_cmd,
            rc,
            stdout.strip(),
            stderr.strip(),
        )
    return resp


def log_connection_diagnostics(modem_idx, iface):
    """Log modem/network state to help debug a failed IP acquisition."""
    logging.info("[DIAG] ---- connection diagnostics ----")
    for cmd in ("AT+CGATT?", "AT+CGACT?", "AT+CGDCONT?", "AT+CGPADDR=1"):
        resp = run_at_query(modem_idx, cmd)
        logging.info("[DIAG] %s -> %s", cmd, resp)

    _, link_stdout, _ = run_cmd(["ip", "-s", "link", "show", "dev", iface])
    logging.info(
        "[DIAG] ip -s link show dev %s:\n%s", iface, link_stdout.strip()
    )

    _, dmesg_stdout, _ = run_cmd(["sudo", "sh", "-c", "dmesg | tail -n 40"])
    logging.info("[DIAG] dmesg (tail):\n%s", dmesg_stdout.strip())
    logging.info("[DIAG] ---------------------------------")


def deprioritize_default_route(iface, metric=200):
    """Raise the metric of the default route DHCP installed on iface.

    A DHCP lease on the WWAN interface can install a default route that
    outranks the DUT's management interface (e.g. a lower metric than
    the control network), hijacking all default-routed traffic. Since
    this test always targets iface explicitly (ping -I / mmcli), it
    doesn't need to win the global default route race, so push its
    metric up to keep the management route preferred.
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
            "sudo",
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


def detect_module(config):
    """Return (module_name, at_steps) for the first name found in mmcli -L.

    The module name key is matched literally against mmcli -L output.
    Exits with an error if no configured module is detected.
    """
    rc, stdout = mmcli_list()
    if rc != 0:
        logging.error("mmcli -L failed (rc=%s)", rc)
        sys.exit(1)
    for name, at_steps in config.items():
        if name in stdout:
            logging.info("Detected module: %s", name)
            return name, at_steps
    logging.error(
        "No configured WWAN module found in mmcli -L output:\n%s",
        stdout.strip(),
    )
    sys.exit(1)


def run_at_step(modem_idx, name, spec, env, timeout=15):
    """Execute one AT-command step; return True on pass.

    `spec` is either a plain AT command string (pass = any response
    came back), or a dict {"cmd": <AT command>, ...} for steps that
    need to validate the actual value, not just presence of a
    response:
      - "expect": <substring> the response must contain
      - "expect_nonempty": True if the response must be non-empty
      - "expect_min": <int> the first number in the response must be >=
      - "poll": True to retry for up to WWAN_SETUPTIME seconds instead
        of failing immediately (e.g. GPRS attach / PDP context /
        IP assignment can take a few seconds after auto-dial is set)
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
        rc, stdout, stderr = mmcli_at(modem_idx, cmd, timeout=timeout)
        resp = parse_response(stdout)
        logging.info("[AT] rc=%s stdout=%s", rc, stdout.strip())
        if stderr.strip():
            logging.info("[AT] stderr=%s", stderr.strip())

        if expect is not None:
            passed = rc == 0 and resp is not None and expect in resp
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
            passed = rc == 0 and resp is not None

        if passed or not poll or time.time() >= deadline:
            break
        time.sleep(interval)

    if passed:
        logging.info("[PASS] %s", name)
    else:
        logging.error("[FAIL] %s: rc=%s resp=%s", name, rc, repr(resp))
    return passed


def run_ping(iface, modem_idx):
    """Bring up iface, wait for a DHCP lease, then ping 8.8.8.8.

    The DUT's own network manager (NetworkManager, per the boards'
    provisioning config) already auto-configures new interfaces via
    DHCP; a reboot alone brings the IP back, confirming NetworkManager
    (not this script) owns the lease. So this does not run its own
    DHCP client or flush the address (which was tearing down NM's
    state without it recovering on its own); it only nudges
    NetworkManager to (re)connect the device and waits for the lease.
    """
    # 1. Bring the link UP
    logging.info("[NET] Bringing up interface %s ...", iface)
    rc, _, stderr = run_cmd(["sudo", "ip", "link", "set", iface, "up"])
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
    run_cmd(["sudo", "nmcli", "device", "connect", iface])

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
        log_connection_diagnostics(modem_idx, iface)
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


def run_steps(modem_idx, at_steps, env):
    """Run all AT steps then ping; return list of pass/fail bools.

    at_steps is a dict of {step_name: at_command}.
    """
    results = []
    for name, cmd in at_steps.items():
        ok = run_at_step(modem_idx, name, cmd, env)
        results.append(ok)
        if not ok:
            logging.error("Aborting: AT command '%s' failed", name)
            return results
    results.append(run_ping(env["WWAN_NET_IF"], modem_idx))
    return results


def send_reset(modem_idx):
    """Send AT+CRESET; return True if ModemManager accepted the command."""
    logging.info("[RESET] Sending AT+CRESET to modem %s ...", modem_idx)
    rc, stdout, stderr = mmcli_at(modem_idx, "AT+CRESET", timeout=10)
    resp = parse_response(stdout)
    logging.info("[RESET] rc=%s stdout=%s", rc, stdout.strip())
    if stderr.strip():
        logging.info("[RESET] stderr=%s", stderr.strip())
    if rc != 0:
        logging.error("[FAIL] AT+CRESET failed (rc=%s)", rc)
        return False
    logging.info("[PASS] AT+CRESET accepted (response=%r)", resp)
    return True


def verify_cops(modem_idx, timeout):
    """Verify AT+COPS? responds (any response) within `timeout` seconds."""
    logging.info("[RESET] Verifying AT+COPS? responds within %ss ...", timeout)
    rc, stdout, stderr = mmcli_at(modem_idx, "AT+COPS?", timeout=timeout)
    resp = parse_response(stdout)
    logging.info("[RESET] AT+COPS? rc=%s stdout=%s", rc, stdout.strip())
    if stderr.strip():
        logging.info("[RESET] stderr=%s", stderr.strip())
    return rc == 0 and resp is not None


def radio_cycle(modem_idx, wait_seconds):
    """Cycle the radio (AT+CFUN=4 then 1) to nudge a stuck registration."""
    logging.info("[RESET] Cycling radio: AT+CFUN=4 -> AT+CFUN=1 ...")
    mmcli_at(modem_idx, "AT+CFUN=4", timeout=10)
    time.sleep(3)
    mmcli_at(modem_idx, "AT+CFUN=1", timeout=10)
    logging.info(
        "[RESET] Waiting %ss for the radio to come back up ...",
        wait_seconds,
    )
    time.sleep(wait_seconds)


def wait_for_registration(modem_idx, timeout, radio_cycle_wait, interval=5):
    """Poll registration state; do one radio cycle if it stays denied.

    Returns (passed, registration, operator_id).
    """
    deadline = time.time() + timeout
    cycled = False
    registration = operator_id = None
    while True:
        registration = get_field(modem_idx, "registration")
        operator_id = get_field(modem_idx, "operator id")
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
                radio_cycle(modem_idx, radio_cycle_wait)
                deadline = time.time() + timeout
                continue
            return False, registration, operator_id
        time.sleep(interval)


def reset_and_recover(hw_id):
    """Run the reset/recovery procedure; return True on success.

    Issues AT+CRESET, waits for the modem to re-enumerate over USB
    (its ModemManager index can change), verifies AT+COPS? responds,
    then waits for network registration, falling back to one AT+CFUN
    radio cycle if registration stays denied for too long.

    Not every module/project needs this (see the has_wwan_reset_recovery
    manifest entry gating the job that calls this), and it needs much
    longer timeouts than the normal connection test, so it's driven by
    its own WWAN_RESET_* environment variables rather than
    WWAN_SETUPTIME.
    """
    reset_wait = int(os.environ.get("WWAN_RESET_WAIT", "30"))
    cops_timeout = int(os.environ.get("WWAN_RESET_COPS_TIMEOUT", "30"))
    denied_timeout = int(os.environ.get("WWAN_RESET_DENIED_TIMEOUT", "120"))
    radio_cycle_wait = int(os.environ.get("WWAN_RESET_RADIO_CYCLE_WAIT", "45"))

    modem_idx = resolve_modem_index(hw_id)
    logging.info("=== WWAN Reset & Recovery Test ===")
    logging.info("Modem index (pre-reset): %s", modem_idx)

    if not send_reset(modem_idx):
        return False

    logging.info(
        "[RESET] Waiting up to %ss for modem to re-enumerate ...",
        reset_wait,
    )
    new_modem_idx = resolve_modem_index_polling(hw_id, timeout=reset_wait)
    if new_modem_idx is None:
        logging.error(
            "[FAIL] Modem with equipment id '%s' did not reappear within"
            " %ss",
            hw_id,
            reset_wait,
        )
        return False
    logging.info("[PASS] Modem reappeared as index %s", new_modem_idx)

    if not verify_cops(new_modem_idx, cops_timeout):
        logging.error(
            "[FAIL] AT+COPS? did not respond within %ss after reset",
            cops_timeout,
        )
        return False
    logging.info("[PASS] AT+COPS? responded after reset")

    ok, registration, operator_id = wait_for_registration(
        new_modem_idx, denied_timeout, radio_cycle_wait
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


def load_config(path):
    """Load and return the JSON module config."""
    with open(path) as fh:
        return json.load(fh)


def parse_args():
    parser = argparse.ArgumentParser(
        description="WWAN module connection test via ModemManager"
    )
    parser.add_argument(
        "hw_id",
        type=str,
        help="The equipment id (IMEI) of the modem, as reported by"
        " mmcli -L / the wwan_resource job",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to the wwan_at_command JSON config (default: taken"
        " from the WWAN_AT_COMMAND_JSON environment variable; a bare"
        " filename is resolved against"
        " $PLAINBOX_PROVIDER_DATA/wwan_at_command/, a full path is"
        " used as-is)",
    )
    parser.add_argument(
        "--action",
        choices=("connect", "reset-recovery"),
        default="connect",
        help="'connect' (default) runs the AT-command connection test;"
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

    if args.action == "reset-recovery":
        sys.exit(0 if reset_and_recover(args.hw_id) else 1)

    if not args.config:
        logging.error(
            "No config path given: set the WWAN_AT_COMMAND_JSON"
            " environment variable (a bare filename resolves against"
            " $PLAINBOX_PROVIDER_DATA/wwan_at_command/) or pass --config"
        )
        sys.exit(1)

    apn = os.environ.get("WWAN_APN", "")
    iface = os.environ.get("WWAN_NET_IF", "")
    if not apn:
        logging.error("Environment variable WWAN_APN is not set")
        sys.exit(1)
    if not iface:
        logging.error("Environment variable WWAN_NET_IF is not set")
        sys.exit(1)

    env = {"WWAN_APN": apn, "WWAN_NET_IF": iface}

    config = load_config(args.config)
    module_name, at_steps = detect_module(config)
    modem_idx = resolve_modem_index(args.hw_id)
    ensure_modem_enabled(modem_idx)

    logging.info("=== WWAN Connection Test ===")
    logging.info("Module      : %s", module_name)
    logging.info("Modem index : %s", modem_idx)
    logging.info("Interface   : %s", iface)
    logging.info("APN         : %s", apn)

    results = run_steps(modem_idx, at_steps, env)

    total = len(results)
    passed_count = sum(1 for r in results if r)
    failed_count = total - passed_count
    if failed_count:
        logging.error(
            "Summary: %d/%d passed - %d test(s) failed",
            passed_count,
            total,
            failed_count,
        )
        sys.exit(1)
    else:
        logging.info(
            "Summary: %d/%d passed - all tests passed",
            passed_count,
            total,
        )


if __name__ == "__main__":
    main()
