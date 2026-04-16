# metabox — Agent Instructions

See the root [`AGENTS.md`](../AGENTS.md) for global rules.
This file adds metabox-specific context.

## What is metabox?

Metabox is an integration-testing tool for Checkbox. It orchestrates
Linux containers (via **LXD**) or virtual machines to run Checkbox
end-to-end in realistic configurations, verifying that Checkbox itself
behaves correctly (not that devices pass tests).

Key entry point: `metabox` CLI (`metabox/main.py`).

## Prerequisites

- A running **LXD** daemon (`sudo snap install lxd && lxd init`).
- Python 3.8+ (uses `pylxd`, `loguru`, `pyyaml`).
- `checkbox-ng` and `checkbox-support` accessible to the containers.

## Installation

```bash
cd metabox
pip install -e .
```

## Running metabox

```bash
metabox <config-file.yaml>
```

Configuration files live in `metabox/configs/`. Each YAML config describes
which scenarios to run and what Checkbox versions to use.

## Project structure

```
metabox/
├── metabox/         # Python package
│   ├── core/        # Container/VM lifecycle, scenario runner
│   ├── scenarios/   # Individual test scenarios
│   └── main.py      # CLI entry point
├── configs/         # Example YAML configuration files
└── pyproject.toml
```

## Formatting

```bash
black --check --line-length 79 metabox/
```

## Key constraints

- **No unit-test framework is wired up yet**: metabox tests are integration
  tests that require LXD. Do not expect a simple `pytest` run in this
  directory to cover meaningful functionality.
- **Scenario files** in `metabox/scenarios/` follow a class-based pattern
  matching existing scenarios. Follow that pattern when adding new scenarios.
- **LXD image caching**: containers are created from LXD images; changes
  that affect image selection or container configuration should be tested
  manually before merging.
- **urllib3 version pin**: `pyproject.toml` pins `urllib3 >= 1.26.0, < 2.0.0`
  for `pylxd` compatibility. Do not upgrade urllib3 without verifying pylxd
  still works.

## Common pitfalls

- Running metabox without a configured LXD daemon will fail immediately with
  a connection error; this is expected, not a code bug.
- Metabox changes rarely warrant the `(Breaking)` marker; use `(Infra)` for
  tooling/CI changes and `(BugFix)` / `(New)` for scenario changes.
