#!/usr/bin/env python3
"""Generic switchdev fabric tests for Linux-switch devices.

All sub-commands operate on any switchdev-capable device (ports exposing
phys_switch_id). Device and test-setup specifics come from ONE setup config
JSON (checkbox config var SWITCHDEV_SETUP_CONFIG; bare filenames are resolved
against $PLAINBOX_PROVIDER_DATA, schema: data/switchdev-setup.schema.json).
Designed for a permanent test setup whose bridge/VLAN layout is set once at
boot and never modified: tests only use link state, netns, and traffic - no
`bridge vlan` changes.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time


def run(cmd, check=True, netns=None):
    if netns:
        cmd = ["ip", "netns", "exec", netns] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise SystemExit(
            "command failed: {}\n{}".format(" ".join(cmd), result.stderr)
        )
    return result


def ip_json(args, netns=None):
    return json.loads(run(["ip", "-j"] + args, netns=netns).stdout or "[]")


def load_config(path, required=True):
    """Load the setup config JSON. Bare filenames resolve against
    $PLAINBOX_PROVIDER_DATA so per-project files can ship in data/."""
    if not path:
        if required:
            raise SystemExit(
                "FAIL: set SWITCHDEV_SETUP_CONFIG in the checkbox config "
                "(path or data/ filename of the setup config JSON)"
            )
        return {}
    if not os.path.exists(path) and not os.path.isabs(path):
        candidate = os.path.join(
            os.environ.get("PLAINBOX_PROVIDER_DATA", ""), path
        )
        if os.path.exists(candidate):
            path = candidate
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(
            "FAIL: cannot load setup config {}: {}".format(path, exc)
        )


def cfg_get(cfg, *keys):
    node = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise SystemExit(
                "FAIL: setup config missing required key: " + ".".join(keys)
            )
        node = node[key]
    return node


def fabric_ports():
    """All netdevs exposing phys_switch_id, i.e. switch fabric ports."""
    ports = []
    for link in ip_json(["-d", "link", "show"]):
        if link.get("phys_switch_id"):
            ports.append(link)
    return ports


def check_reserved_sane(reserved):
    """A reserved entry that matches no real netdev is a placeholder or
    typo: the protection it should provide is silently OFF. Fail loudly.
    Compared against ALL netdevs (an OOB management NIC need not be a
    fabric port)."""
    bogus = sorted(set(reserved) - set(os.listdir("/sys/class/net")))
    if bogus:
        raise SystemExit(
            "FAIL: reserved_ports entries match no netdev (placeholder "
            "or typo - the infra-port protection is not active): "
            + " ".join(bogus)
        )


def cmd_resource(args):
    reserved = set(
        load_config(args.config, required=False).get("reserved_ports", [])
    )
    for link in fabric_ports():
        name = link["ifname"]
        print("interface: {}".format(name))
        print("switch_id: {}".format(link["phys_switch_id"]))
        print("reserved: {}".format(name in reserved))
        print()


def cmd_port_count(args):
    cfg = load_config(args.config)
    expected = cfg_get(cfg, "expected_ports")
    found = sorted(p["ifname"] for p in fabric_ports())
    print("fabric ports ({}): {}".format(len(found), " ".join(found)))
    check_reserved_sane(cfg.get("reserved_ports", []))
    if len(found) != expected:
        raise SystemExit(
            "FAIL: expected {} fabric ports, found {}".format(
                expected, len(found)
            )
        )
    print("PASS")


def operstate(interface):
    with open("/sys/class/net/{}/operstate".format(interface)) as f:
        return f.read().strip()


def wait_link_up(interface, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if operstate(interface) == "up":
            return True
        time.sleep(0.5)
    return False


def cmd_link_flap(args):
    interface = args.interface
    # required=True: this job is manifest-gated on the wired test setup,
    # so a missing config is an operator error - refuse rather than run
    # with an empty reserved list (which would allow flapping the SSH
    # uplink).
    reserved = load_config(args.config).get("reserved_ports", [])
    check_reserved_sane(reserved)
    if interface in reserved:
        raise SystemExit(
            "FAIL: refusing to flap reserved infra port " + interface
        )
    if operstate(interface) != "up":
        print(
            "SKIP-AS-PASS: {} has no link before test, flap not "
            "meaningful (empty port)".format(interface)
        )
        return
    try:
        for i in range(args.iterations):
            run(["ip", "link", "set", interface, "down"])
            time.sleep(args.settle)
            run(["ip", "link", "set", interface, "up"])
            if not wait_link_up(interface, args.timeout):
                raise SystemExit(
                    "FAIL: {} did not recover link after flap {}/{}".format(
                        interface, i + 1, args.iterations
                    )
                )
    finally:
        run(["ip", "link", "set", interface, "up"], check=False)
    print(
        "PASS: {} recovered link after {} admin flaps".format(
            interface, args.iterations
        )
    )


def normalized_vlans():
    entries = []
    for item in json.loads(
        run(["bridge", "-j", "vlan", "show"]).stdout or "[]"
    ):
        for vlan in item.get("vlans", []):
            entries.append(
                (
                    item["ifname"],
                    vlan["vlan"],
                    tuple(sorted(vlan.get("flags", []))),
                )
            )
    return sorted(entries)


def cmd_vlan_drift(args):
    baseline_path = cfg_get(load_config(args.config), "vlan_baseline")
    current = normalized_vlans()
    if not current:
        raise SystemExit(
            "FAIL: live bridge VLAN table is empty - the frozen boot "
            "config did not apply (or vlan_filtering is off)"
        )
    if args.save:
        parent = os.path.dirname(baseline_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(baseline_path, "w") as f:
            json.dump(current, f, indent=1)
        print("baseline saved to {}".format(baseline_path))
        return
    if not os.path.exists(baseline_path):
        raise SystemExit(
            "FAIL: baseline {} missing. Create it once on a known-good "
            "frozen boot config with:\n  switchdev_test.py vlan-drift "
            "--config {} --save".format(baseline_path, args.config)
        )
    with open(baseline_path) as f:
        baseline = [(e[0], e[1], tuple(sorted(e[2]))) for e in json.load(f)]
    missing = set(baseline) - set(current)
    extra = set(current) - set(baseline)
    for entry in sorted(missing):
        print("MISSING from device: {}".format(entry))
    for entry in sorted(extra):
        print("EXTRA on device:     {}".format(entry))
    if missing or extra:
        raise SystemExit("FAIL: VLAN table drifted from frozen baseline")
    print(
        "PASS: VLAN table matches baseline ({} entries)".format(len(baseline))
    )


def port_stats(interface):
    # Assumption: the switchdev driver reports hardware-forwarded packets
    # in ndo_get_stats64 (true for sparx5/lan969x). A driver exposing HW
    # counters only via ethtool -S would need this adapted.
    links = ip_json(["-s", "link", "show", interface])
    if not links:
        raise SystemExit("FAIL: no such interface: " + interface)
    link = links[0]
    return (
        link["stats64"]["rx"]["packets"],
        link["stats64"]["tx"]["packets"],
    )


def offloaded_fdb_count(bridge):
    count = 0
    for entry in json.loads(
        run(["bridge", "-j", "-d", "fdb", "show", "br", bridge]).stdout or "[]"
    ):
        if "offload" in entry.get("flags", []):
            count += 1
    return count


NETNS = "cbx-switchdev-exit"
# Keep UDP datagrams below the fabric MTU: iperf3's UDP default block size
# is 32 KB, which fragments into ~23 link-layer packets each - inflating
# the mid-port counter check and amplifying loss (one lost fragment kills
# the whole datagram).
UDP_LEN = "1400"


def cmd_offload_proof(args):
    """B6-V1: DUT-sourced traffic through the permanently wired chain.

    Moves the pre-provisioned exit SVI into a netns, runs iperf3 across the
    chain, and asserts (a) traffic actually traversed, (b) hardware-offloaded
    FDB entries exist, (c) mid-chain port counters saw the traffic.
    CPU/softirq is NOT asserted here: the DUT itself sources the packets.
    """
    cfg = load_config(args.config)
    bridge = cfg.get("bridge", "br0")
    chain = cfg_get(cfg, "chain")
    entry, exit_, entry_ip, exit_ip, mid_port = (
        cfg_get(cfg, "chain", key)
        for key in ("entry_svi", "exit_svi", "entry_ip", "exit_ip", "mid_port")
    )
    reserved = cfg.get("reserved_ports", [])
    if mid_port in reserved:
        raise SystemExit(
            "FAIL: chain.mid_port {} is a reserved infra port".format(mid_port)
        )
    rate = args.rate or chain.get("rate", "500M")
    mid_rx0, mid_tx0 = port_stats(mid_port)
    run(["ip", "netns", "del", NETNS], check=False)
    run(["ip", "netns", "add", NETNS])
    server = None
    try:
        run(["ip", "link", "set", exit_, "netns", NETNS])
        run(["ip", "addr", "add", exit_ip, "dev", exit_], netns=NETNS)
        run(["ip", "link", "set", exit_, "up"], netns=NETNS)
        run(["ip", "addr", "replace", entry_ip, "dev", entry])
        run(["ip", "link", "set", entry, "up"])
        peer = exit_ip.split("/")[0]
        failures = []
        total_sent = 0
        # UDP on purpose: a fixed offered rate keeps sent/lost assertable
        # (TCP adapts and hides loss). Run BOTH directions - the chain's
        # reverse path is otherwise untested.
        for direction, extra in (("forward", []), ("reverse", ["-R"])):
            server = subprocess.Popen(
                ["ip", "netns", "exec", NETNS, "iperf3", "-s", "-1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            result = run(
                [
                    "iperf3",
                    "-c",
                    peer,
                    "-u",
                    "-b",
                    rate,
                    "-l",
                    UDP_LEN,
                    "-t",
                    str(args.duration),
                    "--connect-timeout",
                    "10000",
                    "--json",
                ]
                + extra
            )
            server.wait(timeout=30)
            server = None
            try:
                report = json.loads(result.stdout)
                sent = report["end"]["sum"]["packets"]
                lost = report["end"]["sum"]["lost_packets"]
            except (ValueError, KeyError, TypeError) as exc:
                raise SystemExit(
                    "FAIL: cannot parse iperf3 {} report: {}".format(
                        direction, exc
                    )
                )
            loss_pct = 100.0 * lost / sent if sent else 100.0
            total_sent += sent
            print(
                "{}: sent={} lost={} ({:.2f}%)".format(
                    direction, sent, lost, loss_pct
                )
            )
            if loss_pct > args.max_loss:
                failures.append(
                    "{} loss {:.2f}% > {}%".format(
                        direction, loss_pct, args.max_loss
                    )
                )
        sent = total_sent
        offloaded = offloaded_fdb_count(bridge)
        mid_rx1, mid_tx1 = port_stats(mid_port)
        mid_seen = (mid_rx1 - mid_rx0) + (mid_tx1 - mid_tx0)
        print(
            "offloaded_fdb={} mid_port_packets={} (total sent={})".format(
                offloaded, mid_seen, sent
            )
        )
        if offloaded < args.min_offloaded:
            failures.append(
                "only {} offloaded FDB entries (need >= {})".format(
                    offloaded, args.min_offloaded
                )
            )
        if mid_seen < sent:
            failures.append(
                "mid-chain port {} saw {} packets < {} sent - traffic "
                "did not traverse the fabric chain".format(
                    mid_port, mid_seen, sent
                )
            )
        if failures:
            raise SystemExit("FAIL: " + "; ".join(failures))
        print("PASS: chain traffic hardware-forwarded")
    finally:
        # Restore the frozen-config state even on failure. Order matters:
        # kill the server so nothing holds the netns, then move the
        # (virtual!) SVI back to the root namespace BEFORE deleting the
        # netns - netns deletion destroys virtual devices left inside it,
        # so the netns is only deleted once the move-back succeeded.
        if server is not None and server.poll() is None:
            server.kill()
            server.wait()
        moved_back = run(
            ["ip", "-n", NETNS, "link", "set", exit_, "netns", "1"],
            check=False,
        )
        if moved_back.returncode == 0:
            run(["ip", "netns", "del", NETNS], check=False)
            run(["ip", "addr", "del", exit_ip, "dev", exit_], check=False)
            run(["ip", "link", "set", exit_, "down"], check=False)
        else:
            print(
                "WARNING: could not move {} back to the root namespace; "
                "keeping netns {} so the device is recoverable "
                "manually".format(exit_, NETNS)
            )
        run(["ip", "addr", "del", entry_ip, "dev", entry], check=False)
        run(["ip", "link", "set", entry, "down"], check=False)


def bridge_port_state(interface):
    link = json.loads(
        run(["bridge", "-j", "link", "show", "dev", interface]).stdout or "[]"
    )
    return link[0].get("state", "unknown") if link else "unknown"


def cmd_stp_fixture(args):
    """B8: bring up the pre-provisioned same-VLAN loop pair under STP.

    The fixture pair sits admin-down in the frozen boot config. Kernel
    (classic 802.1D) STP is enabled for the test and restored afterwards;
    no VLAN change happens. RSTP via mstpd is a planned upgrade.
    Note: asserts the KERNEL bridge port state; whether the driver
    offloads the blocking state to the ASIC is validated on real hardware
    by the absence of a storm during the run.
    """
    cfg = load_config(args.config)
    bridge = cfg.get("bridge", "br0")
    ports = cfg_get(cfg, "stp_fixture_ports")
    if len(ports) != 2:
        raise SystemExit("FAIL: stp_fixture_ports must list exactly 2 ports")
    port_a, port_b = ports
    for port in (port_a, port_b):
        if operstate(port) == "up":
            raise SystemExit(
                "FAIL: fixture port {} is up in default state - test setup "
                "mis-configured, aborting to avoid a live loop".format(port)
            )
    stp_path = "/sys/class/net/{}/bridge/stp_state".format(bridge)
    try:
        with open(stp_path) as f:
            saved_stp = f.read().strip()
    except OSError as exc:
        raise SystemExit("FAIL: {} is not a bridge: {}".format(bridge, exc))
    if saved_stp == "2":
        raise SystemExit(
            "FAIL: bridge {} runs user-space STP (stp_state 2, e.g. "
            "mstpd); this job drives kernel STP only and cannot restore "
            "stp_state 2 afterwards - skip it on this setup".format(bridge)
        )
    try:
        run(["ip", "link", "set", bridge, "type", "bridge", "stp_state", "1"])
        run(["ip", "link", "set", port_a, "up"])
        run(["ip", "link", "set", port_b, "up"])
        deadline = time.time() + args.timeout
        blocked = forwarding = None
        states = {}
        while time.time() < deadline:
            states = {p: bridge_port_state(p) for p in (port_a, port_b)}
            blocking = [p for p, s in states.items() if s == "blocking"]
            fwd = [p for p, s in states.items() if s == "forwarding"]
            if blocking and fwd:
                blocked, forwarding = blocking[0], fwd[0]
                break
            time.sleep(2)
        if not blocked:
            raise SystemExit(
                "FAIL: STP never blocked one side of the loop "
                "(states: {})".format(states)
            )
        print(
            "loop contained: {} blocking, {} forwarding".format(
                blocked, forwarding
            )
        )
        run(["ip", "link", "set", forwarding, "down"])
        start = time.time()
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if bridge_port_state(blocked) == "forwarding":
                print(
                    "PASS: failover to {} in {:.1f}s".format(
                        blocked, time.time() - start
                    )
                )
                return
            time.sleep(2)
        raise SystemExit(
            "FAIL: blocked port {} never took over".format(blocked)
        )
    finally:
        run(["ip", "link", "set", port_a, "down"], check=False)
        run(["ip", "link", "set", port_b, "down"], check=False)
        run(
            [
                "ip",
                "link",
                "set",
                bridge,
                "type",
                "bridge",
                "stp_state",
                saved_stp,
            ],
            check=False,
        )


def cmd_l3_offload_probe(_):
    """C2: informational - report whether any route is hardware-offloaded."""
    routes = ip_json(["route", "show"])
    # iproute2 reports hardware offload as "rt_offload" in the flags
    # array (older builds used a bare "offload" attribute - accept both).
    offloaded = [
        r
        for r in routes
        if "rt_offload" in r.get("flags", []) or r.get("offload")
    ]
    print(
        "routes={} hardware-offloaded={}".format(len(routes), len(offloaded))
    )
    print(
        "STATUS: L3 offload {}".format(
            "ACTIVE" if offloaded else "NOT ACTIVE (CPU-path routing)"
        )
    )


def l3mdev_rule_present(family):
    return any(
        rule.get("l3mdev") is not None or rule.get("table") == "l3mdev"
        for rule in ip_json([family, "rule", "show"])
    )


def cmd_vrf_probe(_):
    """C3: informational - report whether the kernel/driver accepts a VRF."""
    name = "cbx-vrf-probe"
    # Creating the first-ever VRF installs persistent l3mdev FIB rules as
    # a kernel side effect; remember whether they existed so the probe can
    # leave the routing-rule chain exactly as found (frozen config!).
    had_rule = {fam: l3mdev_rule_present(fam) for fam in ("-4", "-6")}
    result = run(
        ["ip", "link", "add", name, "type", "vrf", "table", "4242"],
        check=False,
    )
    if result.returncode == 0:
        run(["ip", "link", "del", name], check=False)
        for fam, present_before in had_rule.items():
            if not present_before and l3mdev_rule_present(fam):
                run(
                    ["ip", fam, "rule", "del", "l3mdev", "pref", "1000"],
                    check=False,
                )
        print("STATUS: VRF creation SUPPORTED")
    else:
        print(
            "STATUS: VRF creation NOT SUPPORTED: {}".format(
                result.stderr.strip()
            )
        )


def add_config_arg(parser):
    parser.add_argument(
        "--config",
        default=os.environ.get("SWITCHDEV_SETUP_CONFIG", ""),
        help="setup config JSON (path, or filename under "
        "$PLAINBOX_PROVIDER_DATA); default: $SWITCHDEV_SETUP_CONFIG",
    )


def main():
    # Make checkbox job aborts (SIGTERM) unwind through the try/finally
    # blocks so stateful tests restore link/STP/netns state.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("resource")
    add_config_arg(p)
    p.set_defaults(func=cmd_resource)

    p = sub.add_parser("port-count")
    add_config_arg(p)
    p.set_defaults(func=cmd_port_count)

    p = sub.add_parser("link-flap")
    add_config_arg(p)
    p.add_argument("--interface", required=True)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--settle", type=float, default=1.0)
    p.add_argument("--timeout", type=float, default=15.0)
    p.set_defaults(func=cmd_link_flap)

    p = sub.add_parser("vlan-drift")
    add_config_arg(p)
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_vlan_drift)

    p = sub.add_parser("offload-proof")
    add_config_arg(p)
    p.add_argument(
        "--rate", default="", help="override chain.rate from the setup config"
    )
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--max-loss", type=float, default=1.0)
    p.add_argument("--min-offloaded", type=int, default=1)
    p.set_defaults(func=cmd_offload_proof)

    p = sub.add_parser("stp-fixture")
    add_config_arg(p)
    p.add_argument("--timeout", type=float, default=90.0)
    p.set_defaults(func=cmd_stp_fixture)

    sub.add_parser("l3-offload-probe").set_defaults(func=cmd_l3_offload_probe)
    sub.add_parser("vrf-probe").set_defaults(func=cmd_vrf_probe)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
