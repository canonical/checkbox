<!--
Example Title: Fixed bugged behaviour of checkbox load config (Bugfix)

A Traceability Marker is required as a suffix in the PR title to help understand the impact of your change at a glance.

Pick one of the following:
- Infra: Your change only includes documentation, comments, github actions or metabox
- BugFix: Your change fixes a bug
- New: Your change is a new backward compatible feature, a new test/test plan/test inclusion
- Breaking: Your change breaks backward compatibility.
    - This includes any API change to checkbox-ng/checkbox-support
    - Changes to PXU grammar/field requirements
    - Breaking changes to dependencies in snaps (fwts upgrade for example)

If your change is to providers it can only be (Infra, BugFix or New).

If your change impacts the submission format in Checkbox test reports, ensure that `submission-schema/schema.json` is updated and relevant fields are documented.

Signed commits are required.
  - See CONTRIBUTING.md (https://github.com/canonical/checkbox/blob/main/CONTRIBUTING.md#signed-commits-required) for further instructions.
  - If you are posting your first pull request from a fork of the repository, a Checkbox maintainer (someone with contributor / maintainer / admin rights) will be required to enable CI checks in the repo to be executed.
    - This will be communicated with a comment to the PR of the form `/canonical/self-hosted-runners/run-workflows <SHA-for-HEAD-commit>`
-->

## Description

<!--
Describe your changes here:

- What's the problem solved (briefly, since the issue is where this is elaborated in more detail).
- Introduce your implementation approach in a way that helps reviewing it well.
- Alert the reviewer of any changes that involve data persistence: present examples of file format changes as part of the PR description (e.g. new fields of data stored in unit or submission output).
-->

## Resolved issues

<!--
Note the Jira and GitHub issue(s) resolved by this PR (`Fixes|Resolves ...`).
-->

## Documentation

<!--
Please make sure that...
- Documentation impacted by the changes is up to date (becomes so, remains so).
  - Documentation in the repository, including contribution guidelines.
  - Process documentation outside the repository.
- When breaking changes and other key changes are introduced, the PR having been merged should be broadcast (in demo sessions, IM, Discourse) with relevant references to documentation. This is an opportunity to gather feedback and confirm that the changes and how they are documented are understood.
-->

## Tests

<!--
Please provide:

- The steps to follow so that the reviewer can test on their end
- A list of what tests were run and on what platform/configuration
- Checkbox submissions where applicable
-->
