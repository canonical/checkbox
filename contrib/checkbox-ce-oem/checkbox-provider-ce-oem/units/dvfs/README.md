# DVFS Tests

The DVFS (Dynamic Voltage and Frequency Scaling) tests validate that a
processor's `devfreq` node can switch governors and, for the
governors with a deterministic target frequency, that the frequency
actually follows the switch. The resource job discovers processors
under `/sys/class/devfreq` (or from a per-platform JSON file) and
generates one test job for every eligible (processor, governor) pair.

`dvfs_test.py` is the helper script behind every job below.

## Common setup

Enable the DVFS tests with the `has_processor_dvfs_support` manifest
entry:

```ini
[manifest]
has_processor_dvfs_support = true
```

To inspect the `devfreq` nodes available on the target device, run:

```bash
ls /sys/class/devfreq/
cat /sys/class/devfreq/<node>/available_governors
cat /sys/class/devfreq/<node>/available_frequencies
```

Every processor tested by this suite must expose a non-empty
`available_frequencies` node. The test reads this frequency table as a
common prerequisite for all governors, including `simple_ondemand`.
`simple_ondemand` does not require a particular frequency to be selected,
but the processor must still provide at least one available frequency.

## Discovering processors

Processors are resolved by `resolve_dvfs_processors()` in
`dvfs_test.py`, in one of two ways:

- **Default (no config file)**: every node under
  `/sys/class/devfreq/` that exposes a `governor` file is used, with
  `type` defaulting to `other` and the expected governors taken
  directly from that node's live `available_governors` value.
- **Per-platform JSON file**: when the `DVFS_PROCESSORS_FILE_PATH`
  environment variable is set, entries in its `allowlist` take
  precedence for the configured processor type, optional sysfs path, and
  expected governors. Other valid processors discovered under
  `/sys/class/devfreq/` are included as type `other` unless they are in
  the `denylist`.

### Per-platform JSON file format

See
[`dynamic-voltage-and-frequency-scaling-schema.json`](../../data/dynamic-voltage-and-frequency-scaling/dynamic-voltage-and-frequency-scaling-schema.json)
for the full schema, and the sibling `*.json` files in the same
[`data/dynamic-voltage-and-frequency-scaling/`](../../data/dynamic-voltage-and-frequency-scaling/)
directory for real platform examples (e.g. `cix_p1.json`,
`genio_1200_700_510.json`).

```json
{
    "allowlist": [
        {
            "device_name": "13000000.gpu",
            "type": "gpu",
            "governors": ["userspace", "powersave", "performance", "simple_ondemand"]
        },
        {
            "device_name": "soc:mdla_devfreq",
            "type": "npu",
            "governors": ["userspace", "powersave", "performance", "simple_ondemand"]
        }
    ],
    "denylist": []
}
```

- `device_name` (required): the node name under `/sys/class/devfreq/`,
  or another platform-specific identifier when combined with
  `sysfs_path`.
- `type` (optional): one of `gpu`, `npu`, `vpu`, `other`. Defaults to
  `other` when omitted.
- `sysfs_path` (optional): absolute sysfs path override, used when the
  processor's `devfreq` node is not exposed directly under
  `/sys/class/devfreq/<device_name>`.
- `governors` (required): the list of governors expected to be
  available for this processor; `ce-oem-dvfs/check_dvfs_resource`
  fails if the node's live `available_governors` doesn't match this
  list exactly. Resource records use the node's live governor list.
- `denylist` (optional, top-level): device names to always exclude,
  even if they would otherwise be picked up.

### Required environment variables

Use these variables in the launcher `[environment]` section when a
per-platform JSON file is needed:

| Variable                    | Description                                                                                  | Default |
|------------------------------|-----------------------------------------------------------------------------------------------|---------|
| `DVFS_PROCESSORS_FILE_PATH`  | Path to the per-platform JSON allowlist/denylist file (see above).                             | Not set |

No matter whether the path is relative or absolute, it is looked up
under `$PLAINBOX_PROVIDER_DATA` first (as resolved by
`general_utils.load_json_file()`). If not found there, the path is
used as-is, so an absolute path pointing anywhere on the filesystem
also works.

```ini
[environment]
DVFS_PROCESSORS_FILE_PATH = dynamic-voltage-and-frequency-scaling/genio_1200_700_510.json
```

When `DVFS_PROCESSORS_FILE_PATH` isn't set, every `devfreq` node under
`/sys/class/devfreq/` is used instead (see
[Discovering processors](#discovering-processors)).

## `ce-oem-dvfs/dvfs_resource`

Resource job. Prints one `dvfs_processor_name` / `dvfs_processor_type`
/ `sysfs_path` / `governor` record for every (processor, governor)
pair returned by `resolve_dvfs_processors()`, used to generate the
per-processor, per-governor test jobs below.

## `ce-oem-dvfs/check_dvfs_resource`

Sanity-check job that runs before any generated test job (declared as
a `depends` of the template job). It re-runs the same discovery logic
in debug mode and fails the whole DVFS run early when:

- no `devfreq` node is found under `/sys/class/devfreq/` and no
  `DVFS_PROCESSORS_FILE_PATH` is set, or
- `DVFS_PROCESSORS_FILE_PATH` is set but a listed processor doesn't
  exist at its resolved path, or its live `available_governors`
  doesn't match the `governors` declared for it in the JSON file.

## `ce-oem-dvfs/dvfs_processor_TYPE_NAME-GOVERNOR`

Template job generated from `ce-oem-dvfs/dvfs_resource`; one job per
(processor, governor) pair. Switches the given processor to the given
governor via `dvfs_test.py test` and verifies the switch, adjusting
(and checking) frequency as appropriate for that governor:

- `performance` — `cur_freq` must settle at `max(available_frequencies)`.
- `powersave` — `cur_freq` must settle at `min(available_frequencies)`.
- `userspace` — every entry of `available_frequencies` is written in
  turn and `cur_freq` must match each one.
- `simple_ondemand` — only the governor switch itself is verified,
  since it's a load-driven governor with no deterministic target
  frequency to assert on. The common non-empty `available_frequencies`
  prerequisite still applies.
- any other governor — the job fails even if the governor switch
  itself succeeds, since there's no dedicated verification logic for
  it yet. This is intentional: a new or custom governor must not be
  silently reported as passed just because its name happens to be
  listed in `available_governors`.

The processor's original governor and frequency are always restored
afterwards, even when a check fails.

This job also carries the `also-after-suspend` flag, so it is run
again after a suspend/resume cycle in test plans that include
suspend testing.
