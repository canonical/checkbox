# providers — Agent Instructions

See the root [`AGENTS.md`](../AGENTS.md) for global rules.
This file adds providers-specific context.

## What are providers?

Providers are collections of test-plan and job definitions for Checkbox.
Each provider in this directory is independently installable.

| Provider | Purpose |
|---|---|
| `base/` | Main provider; hardware and OS tests |
| `resource/` | Resource jobs (detect hardware capabilities) |
| `certification-client/` | Ubuntu certification — client-side tests |
| `certification-server/` | Ubuntu certification — server-side tests |
| `docker/` | Docker-related tests |
| `genio/` | Genio (MediaTek) platform tests |
| `gpgpu/` | GPU/GPGPU tests |
| `iiotg/` | Industrial IoT Gateway tests |
| `sru/` | Stable Release Update regression tests |
| `tpm2/` | TPM 2.0 tests |
| `tutorial/` | Tutorial provider for learning Checkbox |

## Provider structure

```
<provider>/
├── manage.py       # Provider management script (validate, build, develop, test)
├── units/          # PXU unit files (jobs, test plans, categories, …)
├── bin/            # Executable scripts (shell, Python) called by jobs
├── data/           # Data files referenced by jobs
└── tests/          # Python unit tests for scripts in bin/
```

## Running tests for a provider

```bash
cd providers/<name>
# Activate a venv that has checkbox-ng and checkbox-support installed, then:
./manage.py validate     # Check PXU syntax
./manage.py test         # ShellCheck + flake8 + Python unit tests
./manage.py test -k <name>  # Run a specific test
```

For the `base` provider, tox handles venv setup automatically:

```bash
cd providers/base
tox -e py312
```

## PXU unit files

Unit files use an RFC 822-style format. Common unit types:

- `job` — a single test job (has `id`, `plugin`, `command`, …)
- `test plan` — an ordered list of jobs
- `template` — a parameterised job generator
- `category` — groups jobs in the TUI
- `manifest entry` — declares a hardware capability

**Validation**: always run `./manage.py validate` after editing `.pxu` files.
Invalid syntax fails CI.

**Namespace**: core provider units use `com.canonical.certification`. Do not
change the namespace of existing units; it is a breaking change.

## Shell scripts (`bin/`)

- All `*.sh` files are checked with **ShellCheck** automatically by
  `./manage.py test`.
- Use `#!/usr/bin/env bash` (or `sh` if POSIX-only) as the shebang.
- Quote variables; avoid unquoted `$VAR` expansions.

## PR marker rules for providers

Provider-only changes may only use `(Infra)`, `(BugFix)`, or `(New)`.
They must never use `(Breaking)`.

## SRU test-plan changes

If you modify `com.canonical.certification::sru` or `::sru-server`, CI
(`pr_validation.yaml`) checks that the PR description contains:

```
## WARNING: This modifies com.canonical.certification::sru
```

(Replace `::sru` with `::sru-server` as appropriate.)

## Hidden manifest entries

Adding a new `manifest entry` with `meta: hidden` requires a corresponding
update to the lab DUT configuration repository
(`canonical/ce-oem-dut-checkbox-configuration`). The `check_missing_manifests`
CI job will trigger a check automatically, but the contributor must coordinate
the DUT config change before the PR is merged.

## Common pitfalls

- `manage.py develop` registers the provider in a `PROVIDERPATH` directory.
  When running interactively, export `PROVIDERPATH` before calling
  `./manage.py develop -d $PROVIDERPATH`.
- The `base` provider tox configuration installs **all** providers from
  `providers/` (via `for provider in ../*`). A broken sibling provider can
  fail the `base` tox run.
- Template units generate jobs at runtime; validate that resource jobs
  referenced in `requires` fields exist in the `resource` provider.
