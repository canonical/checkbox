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

The DUT side is started as:

```
ptp4l -i <interface> -m -s --network_transport=L2 --tx_timestamp_timeout=5 \
    --transportSpecific=<PTP4L_TRANSPORT_SPECIFIC> [--ptp_minor_version=<PTP4L_PTP_MINOR_VERSION>]
```

### Optional environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable                   | Description                                                        | Default |
|----------------------------|--------------------------------------------------------------------|---------|
| `PTP4L_TRANSPORT_SPECIFIC` | `transportSpecific` nibble of the PTP header: `0` (IEEE 1588) or `1` (802.1AS style). The grandmaster must use the same value. | `1` |
| `PTP4L_PTP_MINOR_VERSION`  | Value for `--ptp_minor_version`; only applied when `ptp4l` is version 4 or newer. | Not set |

`PTP4L_TRANSPORT_SPECIFIC` matters because some NICs only hardware-timestamp
one flavour of PTP frame. A Realtek RTL8126 (`r8126` driver, verified on a
Jetson Orin NX carrier) timestamps `transportSpecific=0` frames but never
returns a TX timestamp for otherwise identical `transportSpecific=1` ones, so
`ptp4l` logs `timed out while polling for tx timestamp`, drops to `FAULTY`
and the job never sees an `rms` line. (The RTL8125 uses the same PTP engine
design in its driver but was not verified.) When the job output shows that
message, set the variable to `0` and start the grandmaster with
`--transportSpecific=0` (or without the option) as well.

To check a NIC directly, send one PTPv2 Delay_Req per `transportSpecific`
value from a raw socket with `SO_TIMESTAMPING` and see which one returns a
hardware stamp on the error queue; the `ethtool -T` capability list does not
reveal this.

### Example launcher environment

```ini
[environment]
PTP4L_TRANSPORT_SPECIFIC = 0
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
