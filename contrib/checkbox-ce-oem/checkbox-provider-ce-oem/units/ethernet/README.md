# Ethernet XDP Tests

This directory contains the XDP (eXpress Data Path) test cases for
Ethernet interfaces whose driver supports XDP in native mode. XDP is a
Linux kernel feature (4.8+) that allows running eBPF programs at the
earliest point of the network receive path, before the packet is handed
to the kernel networking stack.

## Overview

The tests drive `xdp-bench` (from the `xdp-tools` package) to verify the
core XDP actions in native mode:

| Action | Job | What it verifies |
|--------|-----|------------------|
| drop | `ce-oem-ethernet/xdp-drop-native-{{ interface }}` | `XDP_DROP` discards packets at the driver level |
| tx | `ce-oem-ethernet/xdp-tx-native-{{ interface }}` | `XDP_TX` bounces packets back out the same interface (hairpin) |
| pass | `ce-oem-ethernet/xdp-pass-native-{{ interface }}` | `XDP_PASS` forwards packets to the kernel stack |
| redirect | `ce-oem-ethernet/xdp-redirect-{{ source }}` | `XDP_REDIRECT` forwards packets to another interface |
| redirect-cpu | `ce-oem-ethernet/xdp-redirect-cpu-{{ interface }}` | `XDP_REDIRECT` to a specific CPU |

## Job list

### Prerequisite checks

- `ce-oem-ethernet/xdp-check-kernel-config` — verifies `CONFIG_BPF`,
  `CONFIG_BPF_SYSCALL` and `CONFIG_BPF_JIT` are enabled in the running
  kernel.
- `ce-oem-ethernet/xdp-dmesg-log` — attaches the full kernel ring buffer
  (`dmesg`) as evidence for the test results.

### Resource job

- `ce-oem-ethernet/xdp-port-pairing` — detects physical Ethernet interfaces
  with link and emits ring-paired `source`/`target` records for the redirect
  test. With fewer than two interfaces no records are emitted (the redirect
  template expands to zero jobs).

### Template jobs

Each template job has a fixed `template-id` (no `{{ }}` variables) and an
expanded `id` (with `{{ }}` variables). All template jobs carry
`flags: also-after-suspend`, so Checkbox auto-generates an
`after-suspend-<id>` variant of each expanded job.

- `ce-oem-ethernet/xdp-drop-native-{{ interface }}` — one job per NETWORK interface.
- `ce-oem-ethernet/xdp-tx-native-{{ interface }}` — one job per NETWORK interface.
- `ce-oem-ethernet/xdp-pass-native-{{ interface }}` — one job per NETWORK interface.
- `ce-oem-ethernet/xdp-redirect-cpu-{{ interface }}` — one job per NETWORK interface.
- `ce-oem-ethernet/xdp-redirect-{{ source }}` — one job per ring-paired source/target pair.

## Test plan

- `ce-oem-ethernet-xdp-automated` — runs all of the above. It is wired
  into the `ce-oem-automated` plan via `nested_part`.

The test plan `include:` lists the template jobs by their `template-id`
(e.g. `ce-oem-ethernet/xdp-drop-native`), which selects every job
instantiated from that template. Because the after-suspend siblings keep
the original `template-id`, the `also-after-suspend` variants run inline
with the normal jobs in the same plan (there is no separate
after-suspend plan).

## Design notes

- **Native mode only.** The jobs run `xdp-bench` in `-m native` mode, so
  there is no `skb`/generic fallback. A native-mode failure is treated as
  a bug.
- **L2 traffic, no IP required.** The tests self-generate a small amount of
  ARP broadcast traffic using a raw `AF_PACKET` socket (no external `arping`
  dependency), so the interfaces under test do not need an IP address or a
  gateway.
- **`no-touch` packet operation.** ARP frames are not IP (ethertype
  `0x0806`), so `xdp-bench`'s `parse-ip`/`swap-macs` operations would ignore
  or drop them. The single-port tests use `-p no-touch` to process every
  frame as-is.
- **Traffic direction.** Single-port actions (drop/tx/pass) send ARP frames
  from the interface under test itself; `redirect` sends frames from the
  *target* interface so they enter the source interface's RX path.
- **Ring pairing.** For `redirect`, interfaces are sorted naturally and each
  redirects to the next; the last redirects back to the first. With two ports
  this yields `end2 -> end3` and `end3 -> end2`.
- **Manifest gating.** All jobs are gated on
  `manifest.has_xdp_native_mode == 'True'`, so they skip cleanly on
  platforms where XDP native mode does not apply.
- **`xdp-bench` availability.** The template jobs require
  `executable.name == 'xdp-bench'` and skip if it is not installed.

## Helper script

The shared logic lives in `bin/xdp_test.py`. It supports two modes:

- `--action pair-ports` — resource-generator mode (used by
  `ce-oem-ethernet/xdp-port-pairing`).
- `--action <drop|tx|pass|redirect|redirect-cpu>` — runs a single XDP action
  against one interface, self-generates L2 traffic, parses the `xdp-bench`
  output, and judges pass/fail.

Each run action prints the exact `xdp-bench` command it executes, so the
test output records what was actually run.
