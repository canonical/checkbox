# Copilot instructions — Checkbox monorepo

## Overview

Checkbox is a hardware certification and testing framework for Ubuntu, maintained
by Canonical. This is a monorepo. Core components are `checkbox-ng`,
`checkbox-support`, `providers/`, `metabox/`, and snap recipes.

---

## Code review checklist

When reviewing a pull request, verify the following:

### PR hygiene

- [ ] The PR title ends with exactly one of `(Infra)`, `(BugFix)`, `(New)`,
  or `(Breaking)` (case-insensitive). CI enforces this but flag it if missing.
- [ ] All commits are GPG-signed (`git log --show-signature`). Unsigned
  commits will be rejected by Canonical self-hosted runners.
- [ ] The PR description fills in all template sections: Description,
  Resolved issues, Documentation, Tests.

### Code quality

- [ ] Python code is formatted with `black --line-length 79`. Violations
  will fail the `black.yml` CI workflow.
- [ ] New Python code passes `flake8` (run via `manage.py test` in providers
  or `tox` in `checkbox-ng`/`checkbox-support`).
- [ ] Shell scripts pass **ShellCheck** (run automatically via `manage.py test`).
- [ ] New public functions/methods have docstrings or doctests.

### Tests

- [ ] New or changed behaviour is covered by tests (`unittest`/`doctest`/
  `pytest`). No exceptions without explicit justification.
- [ ] Tests follow existing patterns in the component being changed.
- [ ] Coverage is not regressed (Codecov bot will comment on the PR).

### Breaking changes

- [ ] Any public API change to `checkbox-ng` or `checkbox-support` must use
  the `(Breaking)` marker.
- [ ] PXU grammar/field changes must use `(Breaking)`.
- [ ] Provider-only changes must use `(Infra)`, `(BugFix)`, or `(New)` —
  never `(Breaking)`.

### SRU test plans

- [ ] If `com.canonical.certification::sru` or `::sru-server` is modified,
  the PR description must contain the exact warning header:
  `## WARNING: This modifies com.canonical.certification::sru`
  (or `::sru-server`). The `pr_validation.yaml` CI check enforces this.

### Submission schema

- [ ] If the change affects the test-report submission format, confirm that
  `submission-schema/schema.json` is updated.

### Hidden manifest entries

- [ ] If a new hidden `manifest entry` unit is added, confirm that the
  contributor is aware that the DUT configuration repository also needs
  updating (see `tools/compare_manifests.py` and the CI check).

### Documentation

- [ ] Prose in `docs/` is wrapped at 80 characters.
- [ ] Significant new features or breaking changes include documentation
  updates or a follow-up issue for docs.

---

## Component-specific notes

### `checkbox-ng/`

- Contains the `plainbox` engine and the `checkbox-cli` entry point.
- Supports Python 3.5 – 3.12; avoid syntax or library features not available
  in Python 3.5 unless the targeted range is being updated.

### `checkbox-support/`

- Helper library imported by both `checkbox-ng` and providers.
- The `checkbox_support/vendor/` subtree is third-party code — do not apply
  project style rules to it and exclude it from coverage reports.

### `providers/`

- Unit definitions live in `units/` as PXU (RFC 822-style) files.
- Scripts live in `bin/`; shell scripts are ShellCheck-verified.
- Each provider has a `manage.py`; run `./manage.py validate` to check PXU
  syntax and `./manage.py test` for linting and unit tests.

### `metabox/`

- Integration-testing tool that requires LXD. Do not expect `metabox` tests
  to pass without a running LXD daemon.

### `contrib/`

- Community-maintained providers. CODEOWNERS in `.github/CODEOWNERS` routes
  reviews to the relevant team.
