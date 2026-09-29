# Thermal Sensor Tests

This directory contains the Checkbox CE OEM thermal test units and test
plans.

## Files in this directory

- `category.pxu`: defines the `thermal` category.
- `jobs.pxu`: defines the thermal resource job, the per-zone temperature
  test template, and the suspend/resume identity checks.
- `test-plan.pxu`: groups the thermal jobs into automated and
  after-suspend plans.

## What the tests do

The thermal test flow has two main goals:

1. Verify that each discovered thermal zone is usable during normal test
   execution.
2. Verify that thermal zone identity remains stable across suspend and
   resume.

### Zone discovery

The `thermal_zones` resource job runs:

```bash
thermal_sensor_test.py dump
```

This enumerates all `thermal_zone*` nodes under `/sys/class/thermal` and
collects metadata including:

- zone name
- zone type
- stable ID
- sysfs path
- device / firmware / DT identity hints
- bound cooling-device types
- whether the temperature is readable (`temp_available`)

### Per-zone temperature test

The template job `ce-oem-thermal/temperature_{stable_id}_{type}` runs:

```bash
thermal_sensor_test.py monitor --stable-id {stable_id} --zone-type "{type}"
```

The helper resolves the current `thermal_zoneN` by using both:

- `stable_id`
- thermal `type`

This is intentional. The test does not rely on `thermal_zone42` staying a
specific zone forever. Instead, it resolves the zone from a more stable
identity derived from sysfs properties.

During execution the script logs both:

- the current zone name, for example `thermal_zone42`
- the thermal type, for example `camera0-thermal`

A zone with no temperature data (`ENODATA`) fails by default; see
`TZ_ALLOW_NO_DATA` below.

### Suspend and resume identity check

Two additional jobs protect the suspend/resume path:

- `ce-oem-thermal/snapshot_before_suspend`
- `after-suspend-ce-oem-thermal/compare_snapshot_after_suspend`

The strategy is:

1. Take a pre-suspend snapshot of all thermal zones.
2. Suspend and resume the system.
3. Take a post-resume snapshot.
4. Compare both snapshots and fail if zone identity changed.

The compare step uses:

```bash
thermal_sensor_test.py compare --before ... --after ... --fail-on-diff
```

This is meant to catch platform regressions where thermal zones are
unexpectedly renumbered, disappear, or come back with changed identity
information after resume.

## How stable identity is derived

The helper computes a `stable_source` using the best available sysfs
identity in this order:

1. `device/of_node`
2. `device/firmware_node/path`
3. `device`
4. thermal `type`

Bound cooling-device types (`cdev*`) are not used: they change with driver
state (for example a GPU devfreq cooling device appears or disappears with
its driver), which would change the stable ID between the resource job and
the test, or between boots.

The final `stable_id` is a hash of:

- thermal type
- stable source

This allows the test to survive `thermal_zoneN` renumbering better than a
plain zone-index lookup.

## Configuring `TZ_IGNORE_TEMP_CHECK`

Some platforms expose readable thermal nodes whose values do not change in
practice during the stress window. In those cases, you can configure the
job to skip the "temperature must change" validation.

The job already exposes this environment variable:

```text
TZ_IGNORE_TEMP_CHECK
```

### Supported values

`TZ_IGNORE_TEMP_CHECK` supports two modes.

Global override:

```text
TZ_IGNORE_TEMP_CHECK=all
```

Type-specific override:

```text
TZ_IGNORE_TEMP_CHECK=cpu-thermal|cpu2-thermal|camera0-thermal
```

Matching is done against the thermal zone `type` string.

### Behavior when enabled

If `TZ_IGNORE_TEMP_CHECK` matches the current thermal type, the monitor job
switches to a readability-only check.

That means the test will:

1. resolve the target thermal zone
2. read the temperature value once
3. pass if the temperature node is readable

It will not:

- require the value to change
- run the stress-based temperature-change loop

This is useful for hardware where the thermal path is valid but the sensor
value is static or too coarse during the test duration.

## How to choose `TZ_IGNORE_TEMP_CHECK`

Use the override only for zones that are known to be readable but not
suitable for change-detection.

Recommended approach:

1. Run the thermal tests normally first.
2. Check the logs for zones that repeatedly stay constant while still
   reading valid temperatures.
3. Add only those thermal types to `TZ_IGNORE_TEMP_CHECK`.
4. Prefer a type-specific list over `all` whenever possible.

Using `all` is broader and should usually be reserved for bring-up or
special debugging scenarios.

## Configuring `TZ_ALLOW_NO_DATA`

Some sensors report no temperature (`ENODATA`) while their power domain is
off, for example an engine that is power-gated when idle. The same error is
returned when a driver failed to power the domain on, so these zones fail by
default.

For zones that are power-gated by design and cannot be powered for the test
(for example, the engine behind the zone does not exist on this board), list
their types in `TZ_ALLOW_NO_DATA` (same syntax as `TZ_IGNORE_TEMP_CHECK`:
`all` or a `|`-separated list of exact thermal types). If the device exists,
use `TZ_KEEP_POWERED` instead. Do not list a zone whose missing data can mean
a broken driver, such as a GPU zone: skipping it hides that failure.

```text
TZ_ALLOW_NO_DATA=cv0-thermal|cv1-thermal|cv2-thermal
```

The `thermal_zones` resource then reports `testable_stable_id: none` for a
listed zone that has no data at discovery, and its temperature job, which
requires `thermal_zones.testable_stable_id == "<its stable_id>"`, is skipped.
Listed zones that do report data are tested normally.

## Configuring `TZ_KEEP_POWERED`

Instead of skipping a power-gated zone, `TZ_KEEP_POWERED` powers the device
that owns its power domain for the duration of the temperature test, so the
zone is really tested. Map each thermal type to one or more device sysfs
paths:

```text
TZ_KEEP_POWERED=<type>:<device>[,<device>]|<type>:<device>
```

Only the first `:` separates the type, so PCI paths such as
`0000:01:00.0` are fine.

For each listed device the test reads `<device>/power/control`:

- `on`: the device is already kept powered and is left untouched.
- anything else (normally `auto`): it is set to `on` before the zone is
  read, and the original value is written back after the test, also when
  the test or the power-on fails (a failed driver resume can still leave
  `on` set).

The test fails if a listed device has no `power/control`, if a write does
not return within 20 s (a driver whose runtime resume hangs), or if the
original value cannot be written back; an earlier error is still the one
reported. A zone listed here is always tested, even if `TZ_ALLOW_NO_DATA`
also lists it.

### Finding the device

1. Find a zone that reports `ENODATA` while the system is idle:
   `cat /sys/class/thermal/thermal_zone*/temp`.
2. Find the device that powers it, for example the GPU for `gpu-thermal`,
   and check that it is runtime-suspended:
   `cat <device>/power/runtime_status` shows `suspended`.
3. Check by hand that powering it makes the zone readable, then restore it:

   ```shell
   cat <device>/power/control              # remember it, usually "auto"
   echo on | sudo tee <device>/power/control
   cat /sys/class/thermal/thermal_zoneN/temp
   echo auto | sudo tee <device>/power/control
   ```

Powering a device runs its driver's runtime resume. If the manual check
above hangs or logs a kernel error, that is a driver bug: file it. With the
device listed, the zone's test then fails with that error (after at most
20 s) instead of blocking the run, and the board may need a reboot
afterwards.

### Examples

```text
# AGX Thor: the GPU (PCI) powers gpu-thermal
TZ_KEEP_POWERED=gpu-thermal:/sys/bus/pci/devices/0000:01:00.0

# AGX Orin: cv0/cv1/cv2 share one CV power domain, one CV engine is enough
TZ_KEEP_POWERED=cv0-thermal:/sys/devices/platform/bus@0/13e00000.host1x/16000000.pva0|cv1-thermal:/sys/devices/platform/bus@0/13e00000.host1x/16000000.pva0|cv2-thermal:/sys/devices/platform/bus@0/13e00000.host1x/16000000.pva0
```

A board without the engine (for example Orin Nano has no DLA/PVA, so its
cv zones never report data) should use `TZ_ALLOW_NO_DATA` instead.

## Manual helper commands

When debugging outside Checkbox, these helper commands are useful.

Dump zones:

```bash
thermal_sensor_test.py dump
```

Take a snapshot:

```bash
thermal_sensor_test.py snapshot -o /tmp/thermal.tsv
```

Compare two snapshots:

```bash
thermal_sensor_test.py compare --before /tmp/before.tsv --after /tmp/after.tsv
```

Monitor a specific stable ID:

```bash
thermal_sensor_test.py monitor --stable-id <stable_id> --zone-type "<type>"
```

Readability-only behavior for selected types:

```bash
TZ_IGNORE_TEMP_CHECK="cpu-thermal|cpu2-thermal" \
thermal_sensor_test.py monitor --stable-id <stable_id> --zone-type "<type>"
```

## Test-plan structure

The thermal test plans are split into:

- `ce-oem-thermal-automated`
- `after-suspend-ce-oem-thermal-automated`

The automated plan includes:

- the pre-suspend snapshot job
- one generated temperature job per discovered zone

The after-suspend automated plan includes:

- the post-resume snapshot compare job
- the same per-zone temperature jobs re-run after suspend

## Practical notes

- The zone name in logs may change across boots or platform revisions.
  The type and stable ID are the more meaningful identifiers.
- `TZ_IGNORE_TEMP_CHECK` is a test-policy override, not a fix for broken
  thermal hardware.
- `TZ_ALLOW_NO_DATA` is also a policy override: only list zones whose power
  domain is expected to be off during the test and cannot be powered with
  `TZ_KEEP_POWERED`.
- If a zone is both unreadable and static, the readability-only path will
  still fail because it must be able to read the temperature node.
