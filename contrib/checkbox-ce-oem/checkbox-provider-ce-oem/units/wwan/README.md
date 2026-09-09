# `wwan_at_command.json` format

This file drives [`bin/usb_hotspot_connection_at_command.py`](../../bin/usb_hotspot_connection_at_command.py),
the script behind the `ce-oem-wwan/usb-hotspot-*` jobs. It targets a
WWAN module attached as a USB cdc-acm device, used purely to bring up
a data connection ("USB hotspot" style), not a full
ModemManager-integrated modem. The script talks to the modem with raw
AT commands only — it does not use ModemManager/`mmcli` at all.

## Top-level structure

```json
{
  "<MODULE_NAME>": {
    "setup": ["<shell command>", ...],
    "connect": {
      "<Step name>": "<AT command>",
      "<Step name>": { "cmd": "<AT command>", ... }
    }
  }
}
```

- **`<MODULE_NAME>`** is a free-form label (e.g. the module's model
  string) used only for logging. The config is expected to have
  exactly one top-level key; if more than one is present, only the
  first is used (a warning is logged) — there is no `ATI`-based
  detection anymore.
- **`setup`** is an ordered list of plain shell command lines run to
  bring the module up (e.g. `modprobe`, `rfkill`, `ip link set ... up`).
  Each command is run through the shell, in order, and execution stops
  at the first command that returns non-zero.
- **`connect`** is the ordered set of AT commands sent directly over
  the module's serial control interface (`WWAN_CONTROL_IF`) to make the
  data connection. Each key is a free-form, human-readable step label
  used only for logging (`[AT] <Step name> -> <cmd>`, `[PASS]/[FAIL]
  <Step name>`). Steps run **in the order they appear in the file**
  (Python/JSON preserve key order) and execution **stops at the first
  failing step**.

**Both `setup` and `connect` are independently optional**, and the
whole config file is optional too (see "Running with no config at all"
below). Whatever ran successfully, the script always finishes by
bringing up `WWAN_NET_IF`, waiting for a DHCP lease, and pinging
`8.8.8.8` — with no config at all (or an empty/all-empty one), this
ping is the entire test. Any provided `setup` or `connect` command that
fails causes the script to exit 1 without ever attempting the ping.

## `connect` step value: plain string vs. spec object

Each step's value is either:

1. **A plain AT command string** — passes as soon as the modem's response
   ends with `OK` (including a bare `OK` with no other data):

   ```json
   "Set auto-dial": "AT+DIALMODE=0"
   ```

2. **A spec object** — use this whenever you need to validate the actual
   value returned, not just that *some* response came back:

   ```json
   "SIM status": { "cmd": "AT+CPIN?", "expect": "READY" }
   ```

   Supported keys (all optional except `cmd`):

   | Key               | Type   | Meaning                                                                 |
   |-------------------|--------|--------------------------------------------------------------------------|
   | `cmd`             | string | The AT command to send. **Required.**                                   |
   | `expect`          | string | Pass only if this substring appears in the response.                    |
   | `expect_nonempty` | bool   | Pass only if the response is non-empty (e.g. an actual IP was returned). |
   | `expect_min`      | int    | Pass only if the first number in the response is `>=` this value.        |
   | `poll`            | bool   | Retry every 3s for up to `WWAN_SETUPTIME` seconds (default 30) instead of failing immediately. Use for values that need time to settle after dialing (attach state, PDP context, IP assignment). |

   If none of `expect` / `expect_nonempty` / `expect_min` are set, the spec
   behaves like a plain string (pass = got any response).

## Special-cased commands

- Any occurrence of the literal placeholder `{APN}` in a `connect` step's
  `cmd` string is substituted with the job's `WWAN_APN` environment
  variable before the command is sent, e.g.:

  ```json
  "Set APN": "AT+CGDCONT=1,\"IP\",\"{APN}\""
  ```

  This isn't tied to a specific command name — use `{APN}` in whatever
  command your module's chipset uses to set the APN (e.g. Quectel's
  `AT+QICSGP=1,1,"{APN}","","",1`), so each module can define its own
  APN-setting command without any script changes. `WWAN_APN` is only
  required (and only read) when `connect` is non-empty.

## Recommended step order

Based on the validated SIM7672G-LNGV bring-up procedure, a full module
entry generally looks like:

```json
{
  "SIM7672G-LNGV": {
    "setup": [
      "modprobe qmi_wwan",
      "rfkill unblock wwan"
    ],
    "connect": {
      "Base communication": "AT",
      "SIM status": { "cmd": "AT+CPIN?", "expect": "READY" },
      "Signal quality": { "cmd": "AT+CSQ", "expect_min": 10 },
      "Network registration": "AT+COPS?",
      "Set APN": "AT+CGDCONT=1,\"IP\",\"{APN}\"",
      "Set auto-dial": "AT+DIALMODE=0",
      "Verify GPRS attachment": { "cmd": "AT+CGATT?", "expect": "CGATT: 1", "poll": true },
      "Verify PDP context active": { "cmd": "AT+CGACT?", "expect": "CGACT: 1,1", "poll": true },
      "Verify IP assignment": { "cmd": "AT+CGPADDR=1", "expect_nonempty": true, "poll": true }
    }
  }
}
```

1. **`setup`** — bring the USB cdc-acm module up at the OS level before
   talking to it (omit entirely if the module is already ready by the
   time the job runs).
2. **Sanity/pre-flight checks** (base comm, SIM ready, signal quality) —
   catch obvious hardware/SIM problems before touching network state.
3. **Network registration** — usually left unvalidated (`expect` omitted),
   since some carriers/roaming SIMs legitimately return an empty operator
   name; only presence of a response is required.
4. **Connection setup** (APN, auto-dial) — configures the module; these
   commands normally return an empty `OK` response.
5. **Post-dial verification, all `poll: true`** — attach, PDP context, and
   IP assignment can take a few seconds after auto-dial is triggered, so
   these retry instead of failing on the first check.

After all `connect` steps pass (or immediately, if `connect` is empty),
the script brings the module's network interface up and waits for the OS
to assign it an address via DHCP, then pings `8.8.8.8` to confirm
end-to-end connectivity. **This final check is not configurable from
this file** — it's the same generic logic every time (interface up →
wait for DHCP lease → deprioritize the resulting default route → ping
`8.8.8.8`), implemented once in
`usb_hotspot_connection_at_command.py`'s `run_ping()`.

## Handling a different WWAN module

Each config file is fully independent (one file per module/device), so
most module-to-module differences in the **`setup`/`connect` steps** — a
Quectel chipset vs. a SIMCom chipset, extra vendor-specific checks, a
different activation/APN command, fewer or more steps, a different
order — can be handled just by writing a new config file, with no script
changes. For example:

```json
{
  "SOME_OTHER_MODULE": {
    "connect": {
      "SIM status": { "cmd": "AT+CPIN?", "expect": "READY" },
      "Set APN and activate": "AT+QICSGP=1,1,\"{APN}\",\"\",\"\",1",
      "Verify IP assignment": { "cmd": "AT+QIACT?", "expect_nonempty": true, "poll": true }
    }
  }
}
```

The generic OS-level connectivity check (interface up/DHCP/ping) still
runs after these steps automatically, the same way for every module.

## Running with no config at all

`WWAN_AT_COMMAND_JSON` is optional. If it's unset (or points at a file
that doesn't exist, or resolves to an empty/all-empty JSON object), the
script skips `setup` and `connect` entirely and just pings over
`WWAN_NET_IF` — useful for a module that's already fully brought up and
connected by the platform itself, where this job only needs to confirm
connectivity.

## Adding a new module

1. Work out what (if anything) is needed to bring the module up at the
   OS level (`modprobe`, `rfkill`, etc.) for the `setup` list.
2. Connect to the target modem's serial control interface directly (e.g.
   `screen /dev/ttyUSB2 115200` or similar) to work out its AT command
   set (vendor AT command reference) for SIM status, signal quality,
   APN, and auto-dial/PDP activation.
3. Validate manually first (e.g. by sending the AT command directly over
   the serial port) so you know the exact expected substrings before
   encoding them in the `connect` steps.
