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
Ethernet segment running `ptp4l` as master, with the same `transportSpecific`
value as the DUT (see below):

```bash
sudo ptp4l -i <if_name_on_host> -m --step_threshold=1 \
    --logAnnounceInterval=0 --logSyncInterval=-3 --network_transport=L2 \
    --transportSpecific=1
```

Wait until it reports `assuming the grand master role` before starting the
DUT jobs.

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

The DUT side is started as:

```
ptp4l -i <interface> -m -s --network_transport=L2 --tx_timestamp_timeout=5 \
    --transportSpecific=<PTP4L_TRANSPORT_SPECIFIC> \
    [--delay_mechanism=<PTP4L_DELAY_MECHANISM>] \
    [--ptp_minor_version=<PTP4L_PTP_MINOR_VERSION>]
```

### Optional environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable                   | Description                                                        | Default |
|----------------------------|--------------------------------------------------------------------|---------|
| `PTP4L_TRANSPORT_SPECIFIC` | `transportSpecific` nibble of the PTP header: `0` (IEEE 1588) or `1` (IEEE 802.1AS / gPTP). The grandmaster must use the same value. | `1` |
| `PTP4L_DELAY_MECHANISM`    | Path-delay mechanism: `E2E` (`Delay_Req`/`Delay_Resp`, ptp4l's default) or `P2P` (peer delay, what 802.1AS uses). The grandmaster must use the same mechanism. | Not set (`E2E`) |
| `PTP4L_PTP_MINOR_VERSION`  | Value for `--ptp_minor_version`; only applied when `ptp4l` is version 4 or newer. | Not set |
| `PTP4L_REARM_HWTSTAMP`     | `1` re-programs hardware timestamping on the interface before the test (`hwstamp_ctl` off then on, `phc_ctl <dev> set` from system time). Workaround for NICs whose PTP engine stays off after a device reset or resume while the driver still reports it enabled (Realtek r8126). Opt-in only: it briefly drops the link and hides a resume finding that the after-suspend job is meant to report. | Not set (off) |

The two variables together select a PTP profile. The standard pairs are
`0` + `E2E` (IEEE 1588 default profile) and `1` + `P2P` (IEEE 802.1AS /
gPTP, which only uses peer delay). The job's historical default, `1` + `E2E`,
is not a defined profile: it runs unchanged for platforms that rely on it,
but `ptp_test.py` prints a warning, because the pair has to be consistent
with what the NIC's hardware timestamping engine accepts. A Realtek RTL8126 (`r8126` driver, verified on a
Jetson Orin NX carrier) hardware-timestamps `transportSpecific=0` frames of
every kind, and `transportSpecific=1` frames of the message types 802.1AS
defines (`Sync`, `Pdelay_Req`, ...), but never returns a TX timestamp for a
`transportSpecific=1` `Delay_Req`, which 802.1AS does not define. With the
default `1` + E2E combination `ptp4l` therefore logs `timed out while
polling for tx timestamp`, drops to `FAULTY` and the job never sees an
`rms` line; the PTP minor version makes no difference. (The RTL8125 uses the
same PTP engine design in its driver but was not verified.) On such a NIC,
either:

- set `PTP4L_TRANSPORT_SPECIFIC = 0` and start the grandmaster with
  `--transportSpecific=0` (or without the option): plain IEEE 1588, E2E; or
- set `PTP4L_DELAY_MECHANISM = P2P` and start the grandmaster with
  `--transportSpecific=1 --delay_mechanism=P2P`: gPTP.

gPTP's peer-delay messages go to the link-local MAC `01:80:C2:00:00:0E`,
which switches and bridges must not forward, so the P2P variant only works
with the grandmaster on the same link (a direct cable, or an 802.1AS-capable
switch). Through an ordinary lab switch the slave stays `UNCALIBRATED`
without any error: the `Pdelay_Req` leaves the DUT but no `Pdelay_Resp` can
come back.

To check a NIC directly, send one PTPv2 event message per combination from a
raw socket with `SO_TIMESTAMPING` and see which ones return a hardware stamp
on the error queue; the `ethtool -T` capability list does not reveal this.

### Example launcher environment

IEEE 1588 profile on a NIC that does not stamp `transportSpecific=1`
`Delay_Req` frames:

```ini
[environment]
PTP4L_TRANSPORT_SPECIFIC = 0
```

gPTP over a direct cable:

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
