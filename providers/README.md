# Main Checkbox providers reviewer guidance

In the interest of making the code uniform and maintainable for at least the
Extended Maintenance Period (ESM) that the tests in the main providers usually
outlive, the following describes the code style we follow. There are examples
of deviation from this style in the main providers, but they either have a
motivation or are candidates for refactoring.

This document is not a replacement for automated linting, it is a supplement.

The following rules are not set in stone, but if you want to bypass them,
you need to provide a clear rationale in the PR or in the comments of the
code itself.

# Dependencies

Dependencies are very painful to manage in Checkbox because every Ubuntu
version still under ESM must be supported. Avoid using dependencies at
all costs.

If a dependency can't be avoided:
- Pick a library that is already packaged, it must be available for
Ubuntu 18.04+.
- If a package is not available, creating it/backporting it is possible in our
PPA but you will have to do it.
- If your dependency has a binary dependency, it must be available for all
architectures we support.
- Even if your test isn't supposed to run on older versions of the OS, your
unit tests may still import it. You must mock it, adding the dependency to
tox.ini is not enough.
- Vendoring is an option, but we would prefer to avoid it.
- Dependencies with side effects (like services) are not acceptable.
- Consider the license of the dependency, Checkbox is GPLv3, the dependency
must be compatible.

# Python tests

In the interest of uniformity, we try to limit the APIs that we use.
Additionally, there are several recurrent issues that we would like to start
catching before landing tests.

- Don't use `os.path`, use `pathlib` instead. [^1]
- Don't use `%` formatting, use `.format` instead. [^1]
- Don't use `os` process management (`system`, `popen` etc.), use `subprocess`. [^1][^2]
- Don't use fixed `time.sleep` beside for polling. Poll instead. [^2]
- Don't destroy command output if possible. [^3]
- Don't wrap `subprocess` calls in your `run_command` function. [^1][^2]
- Don't customize `argparse.ArgumentParser` needlessly. [^1]
- Don't use regexes. [^2]
- Don't disable/ignore linting rules. [^1]
- Don't write anything other than `main()` under `if __name__ == "__main__":` [^1][^4]
- Don't import other `bin/` scripts. Move code to `checkbox-support` instead. [^1]
- Don't `print('error message')` and `exit(1)`. [^1][^2]
`raise SystemExit('error message')` instead.
- Always look if a common utility function is provided by `checkbox-support` [^1]
- Always use `argparse` to parse arguments. [^1]
- Always print a command output that doesn't match the form you expect. [^3]
- Always favour `subprocess.check_...` functions when launching a command. [^2][^3]
- Always favour parsing `json` output rather than free text. [^2][^3]
- Always `slugify` free form text in resources (or at least, always remove
newlines) [^2]
- Always use context managers when doing an action to be undone before exit. [^2][^3]
- Always print parameters if they aren't hardcoded or default (i.e. provided
via Environment variables) [^3]

# PlainboXUnits (PXUs)

Similarly to Python tests, PXUs often expose recurrent issues that we have to
catch at review time. Here are the most common ones

## Checkbox Jobs:

- Don't destructively redirect command output. [^3]
- Don't write nested `for` and `if` in the command section. [^1][^2]
- Don't write bash scripts, use python instead. [^2][^4]
- Don't use `in` in resource expression, prefer adding a new resource fields. [^1][^2]
- Don't use `awk`, limit the use of `sed`. Use python instead. [^1][^2]
- Always declare the environment variables your test needs. [^2][^5]

## Checkbox Templates:
- Don't use jinja. [^1][^2][^3][^5]
- Don't template non-`slugify`d fields in IDs. [^2]
- Always assume there are spaces in resource fields if they weren't explicitly
removed. [^2]
- Always add template fields at the end of the IDs. [^3]

## Checkbox Test Plans:
- Don't rely on Checkbox fixing your dependencies. If your test needs a
dependency, always add it to the test plan. [^5]
- Don't use regex inclusion, use template ids instead. [^5]
- Don't assume tests are going to be executed in the order you include them. [^2]
- Always verify your modification via `list-bootstrapped` and `expand` [^3]


# ODM test requirements

[odm_test_requirements.yaml](odm_test_requirements.yaml) is the primary
catalogue for ODM certification testing preparation, referenced by the ODM
Self-Testing Guide documentation. Update it with relevant job/plan changes; do
not include credentials or confidential information.

## Validate

From the Checkbox repository root:

```bash
uv tool install ./unit_json_schema/validate
validate providers/odm_test_requirements.schema.json providers/odm_test_requirements.yaml
```

The YAML-validation workflow checks only the primary catalogue. Validation
does not read other files or repositories to resolve category, manifest or
job IDs.

## Rules

- One nonempty YAML document, no duplicate keys or unknown fields. Only unknown
fields checked are enforced by the validator.
- `version: 1` and a flat `requirements` list are required. The primary
catalogue also requires `categories`; additional files may add
new categories, but duplicate categories are not allowed.
Category-only files use `categories: []`.
- Categories require `id`, `title` and `description`. Requirements also require
`category`, `ubuntu_versions` and boolean `required`.
- IDs use lowercase letters/digits separated by hyphens. Category and
requirement IDs must each be unique within the file and remain stable.
- Titles are nonempty, single-line, at most 80 characters, without a final
period. Descriptions are nonempty; use folded text (`>`) for readability.
- `required: true` means Required when applicable; `false` means Recommended.
- `ubuntu_versions` accepts `[]` or `["all"]` for unrestricted releases,
quoted `YY.MM` releases, or `==`, `!=`, `>=`, `<=`, `>` and `<` comparisons.
List entries are OR alternatives; comma-separated terms within an entry
are AND, e.g. `[">=22.04,<=26.04"]`. Months must be `01` through `12`;
whitespace around terms/operators is allowed. Reject mixed/repeated `"all"`,
missing/null/scalar values, malformed terms and year-only Core selectors.
- Optional `manifest` is a nonempty list; `related_jobs` is a list. Entries
must be nonempty, whitespace-free strings without duplicates. References
are informational, not applicability expressions.

External category references are allowed by this file-only check. Global ID
uniqueness, no category overrides and resolution of assembled category
references belong to the future converter. Reviewers check job/manifest
references and whether the preparation is sufficient for the tests.

[^1]: Uniformity and maintainability.
[^2]: Recurrent source of bugs.
[^3]: Simplifies debugging/reproducing issues.
[^4]: Bypasses most quality pipelines.
[^5]: Legacy compatibility behaviour now deprecated.
