<!--
Make sure that your PR title is clear and contains a traceability marker.

Traceability Markers is what we use to understand the impact of your change at a glance.
Pick one of the following:
- Infra: Your change only includes documentation, comments, github actions or metabox
- BugFix: Your change fixes a bug
- New: Your chage is a new backward compatible feature, a new test/test plan/test inclusion
- Breaking: Your change breaks backward compatibility.
    - This includes any API change to checkbox-ng/checkbox-support
    - Changes to PXU grammar/field requirements
    - Breaking changes to dependencies in snaps (fwts upgrade for example)
If your change is to providers it can only be (Infra, BugFix or New)

Example Title: Fixed bugged behaviour of checkbox load config (Bugfix)
-->
## Description

<!--
Describe your changes here:

- What's the problem solved (briefly, since the issue is where this is elaborated in more detail).
- Introduce your implementation approach in a way that helps reviewing it well.
-->

## Resolved issues

<!--
Note the Jira and GitHub issue(s) resolved by this PR (`Fixes|Resolves ...`).
Make sure that the linked issue titles & descriptions are also up to date.
-->

## Documentation

<!--
Please make sure that...
- Documentation impacted by the changes is up to date (becomes so, remains so).
  - Documentation in the repository, including contribution guidelines.
  - Process documentation outside the repository.
- Tests are included for the changed functionality in this PR. If to be merged without tests, please elaborate why.
-->

## Tests

<!--
- How was this PR tested? Please provide steps to follow so that the reviewer(s) can test on their end.
- Please provide a list of what tests were run and on what platform/configuration.
- Remember to check the test coverage of your PR as described in CONTRIBUTING.md
-->
