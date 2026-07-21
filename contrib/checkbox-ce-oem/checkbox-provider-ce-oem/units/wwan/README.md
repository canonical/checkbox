# `wwan_at_command.json` format

This file drives [`bin/wwan_connection_at_command.py`](../bin/wwan_connection_at_command.py),
the script behind the `ce-oem-wwan/gsm-connection-at-command-*` jobs. It
defines, per WWAN module, the ordered sequence of AT commands to run over
`mmcli -m <idx> --command=...` to bring up a data connection and verify it.

## Top-level structure

```json
{
  "<MODULE_NAME>": {
    "<Step name>": "<AT command>",
    "<Step name>": { "cmd": "<AT command>", ... }
  }
}
```

- **`<MODULE_NAME>`** must be a substring that appears literally in the
  output of `mmcli -L` for the target modem (e.g. the model name reported
  under `Hardware | model:`). `detect_module()` iterates the JSON keys in
  file order and picks the first key whose name is a substring of the
  `mmcli -L` output, so when multiple keys could match, the one that
  appears first in the file wins.
- **`<Step name>`** is a free-form, human-readable label used only for
  logging (`[AT] <Step name> -> <cmd>`, `[PASS]/[FAIL] <Step name>`).
- Steps run **in the order they appear in the file** (Python/JSON preserve
  key order) and execution **stops at the first failing step** — later
  steps (and the final DHCP/ping check) are skipped.

## Step value: plain string vs. spec object

Each step's value is either:

1. **A plain AT command string** — passes as soon as `mmcli` returns
   `rc == 0` and *any* response (including an empty one, `response: ''`,
   which is how ModemManager reports a bare `OK`):

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

- Any occurrence of the literal placeholder `{APN}` in a `cmd` string is
  substituted with the job's `WWAN_APN` environment variable before the
  command is sent, e.g.:

  ```json
  "Set APN": "AT+CGDCONT=1,\"IP\",\"{APN}\""
  ```

  This isn't tied to a specific command name — use `{APN}` in whatever
  command your module's chipset uses to set the APN (e.g. Quectel's
  `AT+QICSGP=1,1,"{APN}","","",1`), so each module can define its own
  APN-setting command without any script changes.

## Recommended step order

Based on the validated SIM7672G-LNGV bring-up procedure, a full module
entry generally looks like:

```json
{
  "SIM7672G-LNGV": {
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
```

1. **Sanity/pre-flight checks** (base comm, SIM ready, signal quality) —
   catch obvious hardware/SIM problems before touching network state.
2. **Network registration** — usually left unvalidated (`expect` omitted),
   since some carriers/roaming SIMs legitimately return an empty operator
   name; only presence of a response is required.
3. **Connection setup** (APN, auto-dial) — configures the module; these
   commands normally return an empty `OK` response.
4. **Post-dial verification, all `poll: true`** — attach, PDP context, and
   IP assignment can take a few seconds after auto-dial is triggered, so
   these retry instead of failing on the first check.

After all AT steps pass, the script brings the module's network interface
up and waits for the OS to assign it an address via DHCP, then pings
`8.8.8.8` to confirm end-to-end connectivity. **This final check is not
configurable from this file** — it's the same generic logic for every
module (interface up → wait for DHCP lease → deprioritize the resulting
default route → ping `8.8.8.8`), implemented once in
`wwan_connection_at_command.py`'s `run_ping()`. This JSON file only ever
describes the module-specific AT command steps needed to *make* the
connection; it always runs automatically after every AT step in the file
has passed.

## Handling a different WWAN module

Each top-level module key is fully independent, so most module-to-module
differences in the **connection-setup steps** — a Quectel chipset vs. a
SIMCom chipset, extra vendor-specific checks, a different
activation/APN command, fewer or more steps, a different order — can be
handled just by writing a new entry, with no script changes. For example:

```json
{
  "SOME_OTHER_MODULE": {
    "SIM status": { "cmd": "AT+CPIN?", "expect": "READY" },
    "Set APN and activate": "AT+QICSGP=1,1,\"{APN}\",\"\",\"\",1",
    "Verify IP assignment": { "cmd": "AT+QIACT?", "expect_nonempty": true, "poll": true }
  }
}
```

The generic OS-level connectivity check (interface up/DHCP/ping) still
runs after these steps automatically, the same way for every module.

## Adding a new module

1. Run `mmcli -L` and `mmcli -m <idx>` on the target modem to get its exact
   model string.
2. Add a new top-level key using that string (or a distinctive substring
   of it).
3. Work out the module's AT command set (vendor AT command reference) for
   SIM status, signal quality, APN, and auto-dial/PDP activation, adapting
   the `expect*`/`poll` fields as needed for that firmware's response
   format.
4. Validate manually first (e.g. via `mmcli -m <idx> --command="..."`) so
   you know the exact expected substrings before encoding them here.
