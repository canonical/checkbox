#!/usr/bin/env python3
"""PTP clock synchronisation test with ptp4l (linuxptp).

Runs ptp4l as a slave on one Ethernet interface for a fixed time and checks
the offset it reports against the grandmaster ("rms" lines).

Checkbox config variables (launcher [environment]):

  PTP4L_TRANSPORT_SPECIFIC  transportSpecific nibble of the PTP header,
                            0 (IEEE 1588) or 1 (802.1AS/gPTP). Default 1.
                            The grandmaster must use the same value.
  PTP4L_DELAY_MECHANISM     E2E (Delay_Req, ptp4l's default) or P2P
                            (peer delay, what 802.1AS uses). Unset = E2E.
                            Some NICs only hardware-timestamp 802.1AS
                            message types when the nibble is 1, so 1 + E2E
                            never gets a Delay_Req timestamp on them.
  PTP4L_PTP_MINOR_VERSION   passed as --ptp_minor_version on ptp4l >= 4.
"""

import argparse
import os
import re
import subprocess

# Always pass --tx_timestamp_timeout=5: a linuxptp patch increased the
# default TX timestamp timeout from 1 ms to 5 ms because some drivers need
# longer than 1 ms to deliver the hardware TX timestamp, see
# https://www.mail-archive.com/linuxptp-devel@lists.sourceforge.net/msg05015.html
# That patch is only in ptp4l versions later than v2.0, so older versions
# would otherwise still use 1 ms and fail on those drivers.
TX_TIMESTAMP_TIMEOUT_MS = 5
DEFAULT_TRANSPORT_SPECIFIC = "1"
RMS_LINES = 5


def ptp4l_major_version():
    """Major version of the ptp4l binary, or None when it cannot be read."""
    ret = subprocess.run(
        ["ptp4l", "-v"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    match = re.search(r"(\d+)", ret.stdout)
    return int(match.group(1)) if match else None


def build_ptp4l_args(iface, env, ptp4l_major):
    """ptp4l slave command line for iface, from the checkbox config env."""
    transport_specific = env.get(
        "PTP4L_TRANSPORT_SPECIFIC", DEFAULT_TRANSPORT_SPECIFIC
    ).strip()
    if transport_specific not in ("0", "1"):
        raise SystemExit(
            "ERROR: PTP4L_TRANSPORT_SPECIFIC must be 0 or 1, got {!r}".format(
                transport_specific
            )
        )
    args = [
        "-i",
        iface,
        "-m",
        "-s",
        "--network_transport=L2",
        "--tx_timestamp_timeout={}".format(TX_TIMESTAMP_TIMEOUT_MS),
        "--transportSpecific={}".format(transport_specific),
    ]
    delay_mechanism = env.get("PTP4L_DELAY_MECHANISM", "").strip().upper()
    if delay_mechanism:
        if delay_mechanism not in ("E2E", "P2P"):
            raise SystemExit(
                "ERROR: PTP4L_DELAY_MECHANISM must be E2E or P2P, "
                "got {!r}".format(delay_mechanism)
            )
        args.append("--delay_mechanism={}".format(delay_mechanism))
    minor = env.get("PTP4L_PTP_MINOR_VERSION", "").strip()
    if minor:
        if ptp4l_major is not None and ptp4l_major >= 4:
            args.append("--ptp_minor_version={}".format(minor))
        else:
            print(
                "ptp4l version {} does not support --ptp_minor_version, "
                "skipping this option.".format(ptp4l_major)
            )
    return args


def run_ptp4l(args, duration):
    """Run ptp4l for duration seconds and return everything it printed."""
    print("Executing ptp4l for {}s: ptp4l {}".format(duration, " ".join(args)))
    proc = subprocess.Popen(
        ["ptp4l"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    try:
        output, _ = proc.communicate(timeout=duration)
    except subprocess.TimeoutExpired:
        # ptp4l never exits on its own: the timeout is the normal path.
        proc.terminate()
        output, _ = proc.communicate()
    print(output)
    return output


def rms_values(output, last=RMS_LINES):
    """rms offsets (ns) reported in the last `last` lines of ptp4l output."""
    lines = output.strip().splitlines()[-last:]
    values = []
    for line in lines:
        match = re.search(r"\brms\s+(-?\d+)", line)
        if match:
            values.append(abs(int(match.group(1))))
    return values


def run_sync_test(iface, duration, rms_max):
    args = build_ptp4l_args(iface, os.environ, ptp4l_major_version())
    output = run_ptp4l(args, duration)
    values = rms_values(output)
    if not values:
        print("ERROR: unable to get rms value from the ptp4l output")
        print(
            "HINT: make sure a ptp4l grandmaster runs on the same network "
            "segment with the same --transportSpecific value and "
            "--delay_mechanism, and a large enough --logSyncInterval"
        )
        if "timed out while polling for tx timestamp" in output:
            print(
                "HINT: ptp4l never received a hardware TX timestamp for its "
                "delay request. Some NICs (e.g. Realtek RTL8126, r8126 "
                "driver) only timestamp 802.1AS message types when "
                "transportSpecific is 1, so a Delay_Req is never stamped: "
                "either set PTP4L_TRANSPORT_SPECIFIC=0 (IEEE 1588 + E2E) or "
                "PTP4L_DELAY_MECHANISM=P2P (gPTP), on the grandmaster too"
            )
        elif "--delay_mechanism=P2P" in args and "UNCALIBRATED" in output:
            print(
                "HINT: the peer-delay exchange never completed. P2P "
                "messages go to the link-local MAC 01:80:C2:00:00:0E, which "
                "bridges/switches do not forward: the grandmaster must be on "
                "the same link (direct cable or an 802.1AS-capable switch)"
            )
        return 1
    print()
    for rms in values:
        if rms > rms_max:
            print(
                "FAIL: rms value {}ns too big (greater than {}ns)".format(
                    rms, rms_max
                )
            )
            return 1
    print("PASS: rms value is valid. Clock sync succeed.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sync = sub.add_parser(
        "sync", help="synchronise to a grandmaster with ptp4l and check rms"
    )
    sync.add_argument("iface", help="Ethernet interface to run ptp4l on")
    sync.add_argument(
        "--duration", type=int, default=30, help="seconds to run ptp4l"
    )
    sync.add_argument(
        "--rms-max",
        type=int,
        default=1000,
        help="largest acceptable rms offset in ns",
    )
    args = parser.parse_args(argv)
    if args.action == "sync":
        raise SystemExit(
            run_sync_test(args.iface, args.duration, args.rms_max)
        )


if __name__ == "__main__":
    main()
