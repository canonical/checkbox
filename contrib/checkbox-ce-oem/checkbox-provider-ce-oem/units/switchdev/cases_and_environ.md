# Switchdev fabric tests — cases and environ

Generic tests for Linux-switch devices whose ports are exposed through the
kernel switchdev framework (netdevs with `phys_switch_id`), e.g. Microchip
LAN969x/SparX-5 based switches. Nothing here is device-specific: all device
knowledge comes from checkbox config variables and the manifest.

## Design assumptions (the "permanent test setup")

The automated cases assume a permanently wired test setup:

- Front copper ports are self-looped in adjacent pairs with short cables.
- The bridge/VLAN layout is applied **once at boot and never changed**
  ("frozen config"). VLAN pairs and cable pairs interleave, offset by one
  port, so no VLAN ever contains both ends of a cable — the loop cables
  stitch 2-port VLAN segments into one long "chain" entered and exited via
  two pre-provisioned SVIs (or a tagged uplink trunk).
- One reserved port (typically the OOB management netdev, kept OUT of the
  bridge) carries lab/SSH access; tests must never touch it.
- An STP fixture pair may be provisioned: a cabled pair in the SAME VLAN,
  both ports admin-down by default (a deliberate, disarmed loop).
- Tests only use `ip link` state, netns, and traffic — never `bridge vlan`
  commands, so the frozen config is preserved.

## Environ

One variable only:

| Variable | Meaning |
|---|---|
| `SWITCHDEV_SETUP_CONFIG` | The setup config JSON: an absolute path, or a bare filename resolved against the provider `data/` directory (`$PLAINBOX_PROVIDER_DATA`) |

## Setup config JSON

Schema: `data/switchdev-setup.schema.json` · Tactical-1000 example (port names
TODO until the 26.04 image lands): `data/switchdev-setup-tactical1000.json`.
Per-project files follow the `data/switchdev-setup-<project>.json` naming.

| Key | Used by | Meaning |
|---|---|---|
| `bridge` | offload-proof, stp | Bridge device name (default `br0`) |
| `expected_ports` | port-count | Expected number of fabric netdevs (Tactical-1000: 29 = 24 Cu + 4 SFP+ + management) |
| `reserved_ports` | resource, link-flap | Netdev names tests must never touch (infra/management uplink) |
| `vlan_baseline` | vlan-config-drift | Path of the saved known-good `bridge vlan` JSON baseline |
| `chain.entry_svi` / `chain.exit_svi` | chain-offload-proof | Pre-provisioned chain-end SVIs (kept admin-down in the frozen boot config) |
| `chain.entry_ip` / `chain.exit_ip` | chain-offload-proof | CIDR addresses for the two SVIs, same subnet (e.g. 10.101.0.1/24, 10.101.0.2/24) |
| `chain.mid_port` | chain-offload-proof | A fabric port mid-chain whose counters must carry the test traffic |
| `chain.rate` | chain-offload-proof | iperf3 UDP target rate (default 500M) |
| `stp_fixture_ports` | stp-loop-protection | The two fixture pair port names |

Each job requires only the keys it uses and fails with the missing key
path (`FAIL: setup config missing required key: chain.mid_port`).

## Manifest

- `has_switchdev_test_setup` — loop cables in place and frozen chain
  VLAN plan applied at boot.
- `has_switchdev_stp_fixture` — the admin-down same-VLAN fixture pair
  exists in the frozen config.

## Implemented cases

| Job | Needs | What it asserts |
|---|---|---|
| `ce_oem_switchdev_ports` (resource) | switchdev device | Enumerates fabric netdevs; marks reserved ones |
| `port-count` | config var | Fabric netdev count matches the device spec |
| `link-flap-<port>` (template) | link on port | Link recovers after repeated admin down/up; skips empty ports; reserved ports excluded |
| `vlan-config-drift` | test setup manifest + baseline | Live `bridge vlan` table identical to the frozen baseline |
| `chain-offload-proof` | test setup manifest, iperf3 on device | Traffic crosses the loop-cable chain with low loss, FDB entries carry the `offload` flag, a mid-chain port's counters saw the packets (i.e. the ASIC, not a CPU shortcut, forwarded them) |
| `stp-loop-protection` | fixture manifest | Kernel STP blocks one side of the live loop and fails over when the forwarding port drops; bridge STP state restored |
| `l3-offload-probe` | — | Informational: reports whether routes are hardware-offloaded |
| `vrf-probe` | — | Informational: reports VRF support |

## Planned (not yet implemented)

- Forced-speed matrix over loop pairs (10/100/1000 via ethtool).
- Config persistence across warm reboot and PDU cold cycle.
- External offload proof with a directly attached SFP+ iperf3 server
  (adds the CPU-quiet assertion the DUT-sourced variant cannot make).
- FDB learning/aging/capacity (mausezahn MAC ramp), jumbo frames,
  SFP module/EEPROM checks, infra-isolation capture test.
- Performance (NDR/latency) via traffic generator — separate manual test setup.

First target device: Novarq Tactical-1000 (Microchip LAN9696). The full
QA design (topology, VLAN numbering, blockers) lives in the project's
test-case design document.
