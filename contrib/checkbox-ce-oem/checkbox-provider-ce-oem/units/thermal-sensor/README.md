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
4. bound cooling-device types (`cdev*`)
5. thermal `type`

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
- If a zone is both unreadable and static, the readability-only path will
  still fail because it must be able to read the temperature node.
