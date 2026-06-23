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
"""WWAN module connection test driven by wwan_modules.json config."""

import argparse
import json
import logging
import os
import re
import subprocess
import sys

PLAINBOX_PROVIDER_DATA = os.getenv("PLAINBOX_PROVIDER_DATA", "")
DEFAULT_CONFIG = os.path.join(PLAINBOX_PROVIDER_DATA, "wwan_modules.json")


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


def run_at_step(modem_idx, name, cmd, env, timeout=15):
    """Execute one AT-command step; return True on pass."""
    if cmd == "AT+CGDCONT=1":
        cmd = 'AT+CGDCONT=1,"IP","{}"'.format(env["WWAN_APN"])
    logging.info("[AT] %s -> %s", name, cmd)
    rc, stdout, stderr = mmcli_at(modem_idx, cmd, timeout=timeout)
    resp = parse_response(stdout)
    logging.info("[AT] rc=%s stdout=%s", rc, stdout.strip())
    if stderr.strip():
        logging.info("[AT] stderr=%s", stderr.strip())
    passed = rc == 0 and resp is not None
    if passed:
        logging.info("[PASS] %s", name)
    else:
        logging.error("[FAIL] %s: rc=%s resp=%s", name, rc, repr(resp))
    return passed


def run_ping(iface):
    """Bring up iface, obtain a fresh IP via DHCP, then ping 8.8.8.8."""
    # 1. Bring the link UP
    logging.info("[NET] Bringing up interface %s ...", iface)
    rc, _, stderr = run_cmd(["sudo", "ip", "link", "set", iface, "up"])
    if rc != 0:
        logging.error(
            "[NET] Failed to bring up %s: rc=%s stderr=%s",
            iface, rc, stderr.strip(),
        )
        return False

    # 2. Flush stale addresses / routes
    logging.info("[NET] Flushing stale addresses on %s ...", iface)
    run_cmd(["sudo", "ip", "addr", "flush", "dev", iface])

    # 3. Request a fresh IP from the modem via DHCP
    logging.info("[NET] Running dhclient on %s ...", iface)
    rc, stdout, stderr = run_cmd(["sudo", "dhclient", "-v", "-1", iface])
    logging.info("[NET] dhclient rc=%s", rc)
    if stdout.strip():
        logging.info("[NET] dhclient stdout:\n%s", stdout.strip())
    if stderr.strip():
        logging.info("[NET] dhclient stderr:\n%s", stderr.strip())

    # 4. Show resulting address
    _, ip_stdout, _ = run_cmd(["ip", "addr", "show", "dev", iface])
    logging.info("[NET] ip addr show dev %s:\n%s", iface, ip_stdout.strip())

    if not re.search(r"inet\s+\d+\.\d+\.\d+\.\d+", ip_stdout):
        logging.error("[NET] No IP assigned on %s after dhclient", iface)
        return False

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
    results.append(run_ping(env["WWAN_NET_IF"]))
    return results


def load_config(path):
    """Load and return the JSON module config."""
    with open(path) as fh:
        return json.load(fh)


def parse_args():
    parser = argparse.ArgumentParser(
        description="WWAN module connection test via ModemManager"
    )
    parser.add_argument(
        "modem_index",
        type=int,
        help="ModemManager modem index (from: mmcli -L)",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to wwan_modules.json (default: %(default)s)",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args = parse_args()

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

    logging.info("=== WWAN Connection Test ===")
    logging.info("Module      : %s", module_name)
    logging.info("Modem index : %s", args.modem_index)
    logging.info("Interface   : %s", iface)
    logging.info("APN         : %s", apn)

    results = run_steps(args.modem_index, at_steps, env)

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
