# checkbox-ng — Agent Instructions

See the root [`AGENTS.md`](../AGENTS.md) for global rules.
This file adds checkbox-ng-specific context.

## What is checkbox-ng?

`checkbox-ng` is the core Checkbox application. It contains:

- `checkbox_ng/` — the CLI launchers, configuration, remote-agent support,
  and TUI (Urwid-based).
- `plainbox/` — the underlying engine: unit loading, session management,
  provider infrastructure, exporters, and the PXU parser.

Entry point: `checkbox-cli` (defined in `pyproject.toml`).

## Supported Python versions

3.5, 3.6, 3.8, 3.10, 3.12. Do not use syntax or standard-library features
that are unavailable in Python 3.5 unless the supported range is being
explicitly updated.

## Development setup

```bash
cd checkbox-ng
./mk-venv
source venv/bin/activate
# optionally add providers:
PROVIDERPATH=$PWD/../providers/resource/manage.py develop -d $PROVIDERPATH
```

## Running tests

```bash
cd checkbox-ng
tox -e py312          # single version
tox                   # all configured versions
```

Tox installs the package, validates bundled providers, runs `pytest`, and
produces a coverage report. CI runs all versions on each PR that touches
this directory.

## Formatting

```bash
black --check --line-length 79 --extend-exclude '/vendor/' .
```

Run this before pushing; CI will reject non-compliant code.

## Key constraints

- **API stability**: changes to public interfaces in `checkbox_ng/` or
  `plainbox/` that break backward compatibility must use the `(Breaking)` PR
  marker and be flagged explicitly in the description.
- **Remote agent**: `checkbox-cli run-agent` must run as root in production.
  Behaviour changes to remote-agent communication require extra care.
- **Exporters**: changes to any exporter that modify the submission output
  format must be reflected in `submission-schema/schema.json`.
- **Tests required**: every new function or class must have `doctest` or
  `unittest` coverage. The Codecov bot enforces coverage requirements.

## Common pitfalls

- `plainbox/vendor/` contains vendored third-party code. Do not reformat or
  modify it unless intentionally updating the vendor copy.
- The TUI (Urwid) code is sensitive to terminal escape sequences; manual
  testing in a real terminal is advisable for TUI changes.
- `mk-venv` creates the venv; do not confuse it with the tox-managed envs
  in `.tox/`.
