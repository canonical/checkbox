# CE OEM Units: Resource Job Guide

This document describes the recommended pattern for creating resource jobs in
this provider when resource content depends on either:

- user-provided configuration variables, or
- hardware and platform detection.

## Goals

- Resource generation should be robust and non-blocking for plan expansion.
- Resource jobs should not fail a test plan because of parsing/runtime issues.
- A companion check job should validate that resource generation is valid.

## Rule 1: Resource jobs should always return exit code 0

For resource generation, resource jobs should run through `resource_wrapper.sh`.

Why:

- `resource_wrapper.sh` suppresses stderr noise and normalizes behavior.
- Even if the script fails or emits no valid records, the resource job exits
    0.
- This prevents template expansion failures from aborting entire plans.

Pattern:

```pxu
id: my-feature-resource
plugin: resource
command:
    resource_wrapper.sh -- resource_my_feature.sh
```

If configuration is needed, add `environ` and pass those variables to the
script as needed.

## Rule 2: Put resource logic in a script under bin/

Do not keep complex parsing logic inline in PXU. Move it into a script in
`checkbox-provider-ce-oem/bin/`.

Example script skeleton:

```bash
#!/usr/bin/env bash

# Detect hardware and/or parse configuration, then print resource records.
# Example output format:
# key1: value1
# key2: value2
#
# key1: value1b
# key2: value2b

# Optional: configuration checks for resource generation.
# If missing config should only mean "no resource", return 0 and emit nothing.
# If missing config should be treated as an explicit failure, keep that behavior
# for the check job, while the wrapper-based resource job remains non-fatal.

# Emit RFC822-style resource records expected by template-resource jobs.
```

Make scripts executable:

```bash
chmod +x bin/my_feature_resource.sh
```

## Rule 3: Add a companion check job (plugin: shell)

A resource job is intentionally non-fatal. To verify correctness, add a
separate shell check job that runs the same script directly (without wrapper).

Pattern:

```pxu
id: check_my_feature_resource
plugin: shell
command:
    resource_my_feature.sh
```

If needed, add `environ`, `requires`, and `imports` to the check job.

Expected behavior:

- Check job exits non-zero when configuration is invalid, required hardware is
    missing, or resource generation fails.
- Resource job still exits 0 because it is wrapper-based.

## Rule 4: Ensure resource existence is tested

You should validate resource existence with at least one of these:

1. A dedicated check job as shown above (recommended).
2. A downstream functional/template job that depends on generated fields.

Recommended approach is both:

- `check_*_resource` validates generation early.
- Template or test jobs verify generated fields are usable.

## Rule 5: Gate by hardware when appropriate

When a resource is hardware-specific, gate the check and consumer jobs with
manifest-based conditions (and any platform filters needed), for example:

- `imports: from com.canonical.plainbox import manifest`
- `requires: manifest.has_<feature> == 'True'`

This keeps jobs targeted to applicable devices while preserving non-fatal
resource discovery behavior.

## Suggested naming convention

- Resource job: `<feature>_resource` or existing feature-specific naming.
- Check job: `check_<resource-id>_resource` (or close equivalent).
- Resource script: `resource_<feature>.sh` in `bin/`.

## Minimal end-to-end example

```pxu
id: ce-oem-example/device-mapping
plugin: resource
command:
    resource_wrapper.sh -- resource_example_device_mapping.sh

id: check_ce-oem-example_device-mapping_resource
plugin: shell
imports: from com.canonical.plainbox import manifest
requires: manifest.has_example_device == 'True'
command:
    resource_example_device_mapping.sh
```

## Validation checklist

After adding/updating jobs:

```bash
cd contrib/checkbox-ce-oem/checkbox-provider-ce-oem
./manage.py validate
./manage.py test
```

Also verify:

- Resource script is executable.
- Resource output follows expected key/value format.
- Check job fails when resource generation is invalid.
- Check job and consumer jobs are properly gated for hardware-specific flows.
