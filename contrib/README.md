# Contrib Area

## Introduction

This directory, called the “Contrib Area”, contains ongoing projects
(usually Checkbox providers) created and maintained by other teams. These
projects contain executable tests that can in principle be shared publicly,
to expand the certification and regression test coverage across all the
devices in the certification lab.

Each project in the Contrib Area is owned by their original team. These team
can keep contributing to the project by submitting, reviewing and merging PRs.
The Certification team can then adapt (if required, in order to make sure
the tests comply with quality standards set for the Checkbox project) and
move the tests in these projects into the generic providers to make them
part of the Checkbox releases.

## Content of a project directory

In general, it is expected that a project directory is a [Checkbox provider].

Any text content (test scripts, Checkbox jobs, etc.) aimed at being integrated
into the generic Checkbox providers is added to a project directory. Binary
content (sample image data or similar) have to be added using git-lfs. Binary
executable files are not allowed in the monorepo; instead, the source files
to generate these binaries must be provided so they can be compiled against
any architecture Checkbox supports.

For each project directory:

- A GitHub team within the Canonical organization is created with contributors
to this project.
- A matching [CODEOWNERS] section is created so that any modification in
the project directory can be reviewed by the appropriate people or teams.
- If the project directory is a Checkbox provider, its namespace should include
the word “contrib” to show it is not to be used by the Certification
team for testing. In practice, it means editing the namespace information
in the provider’s `manage.py` file, for instance:

```python
#!/usr/bin/env python3
from plainbox.provider_manager import setup, N_

setup(
	name="checkbox-provider-sanity",
	namespace="com.canonical.contrib",
	version="1.0",
	description=N_("Provider for the sanity project"),
	gettext_domain="checkbox-provider-sanity",
)
```

In order to be integrated into the generic providers, the content in a
contrib project directory must comply with the following:

- It cannot contain sensitive information, such as the name of the customer the
content was originally developed for, credentials, or cryptographic secrets.
- Source code must be compatible with the license used by Checkbox ([GNU
GPL 3.0]).
- Copyright information must be stated in the header of the files.
- Canonical and Ubuntu Code of Conduct including inclusive language initiative.


## Continuous integration (CI), continuous deployment (CD), quality and support

Projects in the contrib section of the Checkbox repository will be submitted
to the following CI checks:

- Make sure the provider is valid (by running ./manage.py validate).
- Run code coverage metrics for the scripts present in the provider (in the
bin/ directory). These metrics are for reference only and are not preventing
anything added to the contrib area from being integrated to the main branch.
- Tox run of tests for every python version we support, still non-binding
for landing things.

A GitHub Action can be created for each provider in the contrib area to
automatically trigger builds (for example, if a provider requires a new Debian
package or a Snap package to be built after changes are introduced). These
GitHub Actions are created by the Certification team and maintained afterwards
by the team in charge of the provider (using `CODEOWNERS`), based on the
work already done by the team in charge of the provider (if any).

Certification team is responsible for making the required modifications to
comply with Checkbox quality standards, as defined in [Checkbox contributing
guide], prior to inclusion of their tests into the generic providers (for
instance on moving content from under contrib into locations in the repository
covered by additional quality checks).

In order to prepare for the integration into the Checkbox generic providers,
dedicated CI actions can be put in place in consultation with the contributing
team.

Certification team may request support from the original maintainers of
the tests.

[Checkbox provider]: https://checkbox.readthedocs.io/en/stable/reference/glossary.html#term-Provider
[CODEOWNERS]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
[GNU GPL 3.0]: https://www.gnu.org/licenses/gpl-3.0.en.html
[Checkbox contributing guide]: ../CONTRIBUTING.md
