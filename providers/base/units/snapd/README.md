# Snap Refresh/Revert Tests

## Rationale

Snapd offers the ability to refresh a given snap to a specific revision,
and to revert to the previously installed one if needs be.

Moreover, Snapd has mechanisms in place to automatically refresh every
snap to the latest revision available in their tracked channel. This is
interesting for devices in the field, but also to automatically update a
system that has just been setup, for instance.

In order to test these features, the `snapd` section of Checkbox base
provider offers a test plan, `snap-refresh-revert`, that contains jobs doing
the following:

1. Generate resource information for any gadget, kernel or snapd snap available
on the system; then, if the currently installed revision is different from
the targeted revision and if required (see "Manifest entries" section below):
2. Refresh them again, but this time to their base revision (the revision
that came pre-installed with the image)
3. Revert them back to their original revision
4. Refresh each of these snaps to the revision number from the stable channel
5. Revert them back

After each of these steps, the device is rebooted, then Checkbox checks if
the given snap has been updated to the expected revision before proceeding
the next step.

## Manifest entries

For each of the snap types (gadget, kernel, snapd), a manifest entry controls
whether or not the tests should be executed. If the manifest entries are
not defined, Checkbox will skip every job in the test plan by default. To
enable these tests, the following manifest entries can be set to `true`:

- `need_gadget_snap_update_test`
- `need_kernel_snap_update_test`
- `need_snapd_snap_update_test`

See the [Manifest Entry] section of Checkbox documentation for more
information.

This test plan is aimed at being used during the Snap Update Verification
(SUV) process or the Stable Release Update (SRU) process.

During SUV in particular, the snap that is installed before running the
test plan is from the beta (or the candidate) channel, so it should always
be different from the version in the stable channel or the base version
present on the system.

[Manifest Entry]: https://checkbox.readthedocs.io/en/stable/reference/units/manifest-entry.html
