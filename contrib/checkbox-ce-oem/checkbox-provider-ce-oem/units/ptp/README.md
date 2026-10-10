# PTP Tests

The PTP tests validate IEEE 1588 Precision Time Protocol support on the
Ethernet interfaces of the device: hardware timestamping, the PTP hardware
clock (PHC), and clock synchronisation to a grandmaster with `ptp4l` from
`linuxptp`. The resource job discovers the interfaces with `ethtool -T` and
generates one test job per interface with hardware timestamping.

## Common setup

Enable the PTP tests with the `has_ptp` manifest entry:

```ini
[manifest]
has_ptp = true
```

The test device needs `ethtool` and `ptp4l` (`linuxptp`) in the test
environment. On Ubuntu Classic:

```bash
sudo apt install ethtool linuxptp
```

To check an interface before enabling the tests, run:

```bash
sudo ethtool -T eth0
```

An interface qualifies when the output lists `hardware-transmit`,
`hardware-receive` and `hardware-raw-clock` under `Capabilities`, and a
`PTP Hardware Clock:` number (its `/dev/ptp<N>` device).

The synchronisation jobs need a **grandmaster**: another device on the same
Ethernet segment running `ptp4l` as master with the same PTP profile as the
DUT (see [IEEE 1588 vs IEEE 802.1AS (gPTP)](#ieee-1588-vs-ieee-8021as-gptp)).
For the default profile (IEEE 1588, `transportSpecific=0`, E2E):

```bash
sudo ptp4l -i <if_name_on_host> -m --step_threshold=1 \
    --logAnnounceInterval=0 --logSyncInterval=-3 --network_transport=L2
```

For gPTP add `--transportSpecific=1 --delay_mechanism=P2P` and connect the
grandmaster to the DUT directly (see below). Wait until it reports
`assuming the grand master role` before starting the DUT jobs.

## `ce-oem-ptp/ptp-devices`

Resource job. Lists every Ethernet interface (`e*`) whose `ethtool -T` output
advertises hardware transmit and receive timestamping and a raw hardware
clock, as `eth-interface: <name>` records. The template jobs below are
generated from it.

## `ce-oem-ptp/check-ptp-devices-resource`

Runs the same discovery as a normal job so its output is kept in the
submission.

## `ce-oem-ptp/verify-PTP-support-for-ETH_INTERFACE`

Checks that the interface reports a PTP hardware clock index and that the
matching `/dev/ptp<N>` device exists. Fails when `ethtool -T` reports `none`.

## `ce-oem-ptp/ptp4l-time-sync-for-ETH_INTERFACE-auto`

Runs `ptp4l` as a slave on the interface for 30 seconds
(`ptp_test.py sync <interface>`) and checks the offsets it reports against
the grandmaster: the job passes when the last `rms` values are all within
1000 ns. It depends on the `verify-PTP-support` job for the same interface.

Before starting `ptp4l` the script reads the interface's timestamping
setting (`hwstamp_ctl -i <interface>`). When the driver reports it enabled,
the PTP hardware clock (`/dev/ptp<N>` from `ethtool -T`) must be advancing;
a frozen PHC in that state means the NIC's timestamping engine was switched
off underneath the driver — seen on the Realtek r8126 after every device
reset or suspend/resume — and the job fails immediately with that reason
instead of a timeout or a huge offset. On a fresh boot the setting is off
(the r8126 PHC does not even run until it is enabled, which `ptp4l` does
first thing), so nothing is judged and the test proceeds. The frozen state
is deliberately not repaired automatically: after-suspend PTP jobs exist to
catch exactly that.

On the r8126, enabling timestamping itself drops the link for a few seconds
(`ptp4l` logs `port 1: link down` right after `selected /dev/ptp0 as PTP
clock`, then `link up` about 3.5 s later and starts over). The 30 s run
absorbs that; it is also why `PTP4L_REARM_HWTSTAMP=1` flaps the link.

The DUT side is started as:

```
ptp4l -i <interface> -m -s --network_transport=L2 --tx_timestamp_timeout=5 \
    --transportSpecific=<PTP4L_TRANSPORT_SPECIFIC> \
    [--delay_mechanism=P2P] \
    [--ptp_minor_version=<PTP4L_PTP_MINOR_VERSION>]
```

`--delay_mechanism=P2P` is added when the selected profile uses peer delay;
E2E is `ptp4l`'s own default and is not passed.

### Optional environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable                   | Description                                                        | Default |
|----------------------------|--------------------------------------------------------------------|---------|
| `PTP4L_TRANSPORT_SPECIFIC` | `transportSpecific` nibble of the PTP header: `0` (IEEE 1588) or `1` (IEEE 802.1AS / gPTP). The grandmaster must use the same value. | `0` |
| `PTP4L_DELAY_MECHANISM`    | Path-delay mechanism: `E2E` (`Delay_Req`/`Delay_Resp`) or `P2P` (peer delay). Unset = the mechanism of the selected profile (`E2E` for `0`, `P2P` for `1`). The pair must be a defined profile, see below. The grandmaster must use the same mechanism. | Not set |
| `PTP4L_PTP_MINOR_VERSION`  | Value for `--ptp_minor_version`. The option exists from linuxptp 4.0 (Ubuntu 24.04 noble ships 4.0, 25.04+ ships 4.2); the series-22 runtime carries jammy's linuxptp 3.1.1, where the script skips it and prints `ptp4l version 3 does not support --ptp_minor_version`. linuxptp 3.1.1 always sends PTP version 2.0. | Not set |
| `PTP4L_REARM_HWTSTAMP`     | `1` re-programs hardware timestamping on the interface before the test (`hwstamp_ctl` off then on, `phc_ctl <dev> set` from system time). Workaround for NICs whose PTP engine stays off after a device reset or resume while the driver still reports it enabled (Realtek r8126). Opt-in only: it briefly drops the link and hides a resume finding that the after-suspend job is meant to report. | Not set (off) |

### IEEE 1588 vs IEEE 802.1AS (gPTP)

`ptp4l` speaks one wire protocol (PTPv2) but there are two *profiles* in
common use, and a slave and a grandmaster only synchronise when they run the
same one:

| | IEEE 1588 (default profile) | IEEE 802.1AS / gPTP |
|---|---|---|
| Where it comes from | IEEE 1588-2008/2019, the base PTP standard ("PTP" without qualifier) | IEEE 802.1AS, the TSN / automotive / AVB profile of PTP |
| `transportSpecific` nibble (header byte 0) | `0` | `1` — receivers running the other profile ignore the frame |
| Path-delay mechanism | E2E (`Delay_Req` / `Delay_Resp` to the grandmaster); P2P also allowed (Annex J.4) | P2P only (`Pdelay_Req` / `Pdelay_Resp` to the neighbour) — there is no `Delay_Req` in 802.1AS |
| Destination MAC | `01:1B:19:00:00:00`, forwarded by any switch | peer-delay to `01:80:C2:00:00:0E`, a link-local address that bridges must not forward (full gPTP sends everything there) |
| Network between the two ends | any Ethernet switch works (queuing delay adds jitter, a transparent clock removes it) | direct cable or an 802.1AS-capable (TSN) switch; through an ordinary switch the peer-delay exchange never completes and the slave sits in `UNCALIBRATED` with no error |
| Other differences | two-step or one-step, any sync rate | 8 Sync/s, two-step, `follow_up_info`, neighbour-rate-ratio; `ptp4l` ships the full set as `configs/gPTP.cfg` |
| Typical use | lab / industrial 1588 time sync through a switch | automotive, AVB audio, TSN bridges |

The two variables above select the profile. Defined pairs and what the test
does with them:

| `PTP4L_TRANSPORT_SPECIFIC` | `PTP4L_DELAY_MECHANISM` | Profile | Test behaviour |
|---|---|---|---|
| `0` | unset or `E2E` | IEEE 1588 default profile (Annex J.3) | **default**; grandmaster with no `--transportSpecific` (or `=0`) |
| `0` | `P2P` | IEEE 1588 peer-to-peer default profile (Annex J.4) | accepted; grandmaster with `--delay_mechanism=P2P`, same-link rule applies |
| `1` | `P2P` | IEEE 802.1AS / gPTP | accepted; set both variables (a bare `1` is completed to `P2P`, the only mechanism 802.1AS has); grandmaster with `--transportSpecific=1 --delay_mechanism=P2P` on a direct link |
| `1` | `E2E` | none | **rejected** (`ERROR: PTP4L_TRANSPORT_SPECIFIC=1 marks IEEE 802.1AS ...`) |

`1` + `E2E` was the job's historical, hard-coded combination. It is not a
profile in either standard and it only ever worked on NICs whose PTP engine
ignores the nibble. A Realtek RTL8126 (`r8126` driver, verified on a Jetson
Orin NX carrier) hardware-timestamps `transportSpecific=0` frames of every
kind and `transportSpecific=1` frames of the message types 802.1AS defines
(`Sync`, `Pdelay_Req`, ...), but never returns a TX timestamp for a
`transportSpecific=1` `Delay_Req`: with `1` + E2E `ptp4l` logs `timed out
while polling for tx timestamp`, drops to `FAULTY` and the job never sees an
`rms` line, on a fresh boot too; the PTP minor version makes no difference.
(The RTL8125 uses the same PTP engine design in its driver but was not
verified.) That is why the pair is refused instead of warned about.

To check a NIC directly, send one PTPv2 event message per combination from a
raw socket with `SO_TIMESTAMPING` and see which ones return a hardware stamp
on the error queue; the `ethtool -T` capability list does not reveal this.

### Example launcher environment

IEEE 1588 default profile: nothing to set. The grandmaster runs the command
from [Common setup](#common-setup) as is.

gPTP over a direct cable — set both variables, the profile is the pair
(grandmaster started with `--transportSpecific=1 --delay_mechanism=P2P`):

```ini
[environment]
PTP4L_TRANSPORT_SPECIFIC = 1
PTP4L_DELAY_MECHANISM = P2P
```

## `ce-oem-ptp/ptp4l-time-sync-for-ETH_INTERFACE-manual`

Manual version of the synchronisation test, with the grandmaster and DUT
commands spelled out in the steps. It is kept as a reference and is not
nested in the top-level `ce-oem-manual` plan.

## Test plans

- `ce-oem-ptp-automated` / `after-suspend-ce-oem-ptp-automated`: the
  `verify-PTP-support` and `ptp4l-time-sync-*-auto` jobs.
- `ce-oem-ptp-manual` / `after-suspend-ce-oem-ptp-manual`: the manual
  synchronisation job.
- `ce-oem-ptp-full`: all of the above.
