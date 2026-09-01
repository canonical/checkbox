# checkbox-support — Agent Instructions

See the root [`AGENTS.md`](../AGENTS.md) for global rules.
This file adds checkbox-support-specific context.

## What is checkbox-support?

`checkbox-support` is a Python library of helper utilities used by
`checkbox-ng` and by providers. It provides:

- Hardware information parsers (DMI, udev, PCI, network interfaces, …).
- Image and camera utilities.
- Interactive-command helpers.
- Snap and LXD support utilities.
- `checkbox_support/vendor/` — vendored third-party code (excluded from
  project style rules and coverage).

`checkbox-support` depends on `checkbox-ng`; tox installs `checkbox-ng`
from `../checkbox-ng` before running tests.

## Supported Python versions

3.5, 3.6, 3.8, 3.10, 3.12 (same as checkbox-ng).

## Running tests

```bash
cd checkbox-support
tox -e py312          # single version
tox                   # all configured versions
```

Tests are discovered under `checkbox_support/` by pytest
(`python_files = test_*.py`). The `vendor/` subtree is excluded via
`norecursedirs`.

## Formatting

```bash
black --check --line-length 79 .
```

Do **not** reformat files under `checkbox_support/vendor/`.

## Key constraints

- **API stability**: this library is imported by both `checkbox-ng` and
  many providers. Any breaking change to a public function or class must
  use the `(Breaking)` PR marker.
- **No circular imports**: `checkbox-support` must not import from
  `checkbox-ng` at module level (only `checkbox-ng` may depend on
  `checkbox-support`, not the reverse).
- **vendor/ is read-only**: do not edit files in `checkbox_support/vendor/`
  unless you are intentionally updating the vendor copy and can document
  the upstream source and version.

## Common pitfalls

- Some parsers have strict format expectations tied to real command output
  (e.g., `lspci`, `udevadm`). When changing a parser, provide a realistic
  fixture in the tests rather than a minimal synthetic string.
- `opencv_python` and `numpy` versions are pinned per Python version in
  `tox.ini`. Adding new dependencies must be coordinated with the team to
  keep the version matrix consistent.
