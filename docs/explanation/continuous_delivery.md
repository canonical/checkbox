# Continuous delivery of Checkbox

## Axioms

* a tag can be attached to one unique version in git
* "risk" annotation like "beta" doesn't uniquely identify a version

## Assertions

* two deliverables with the same version string have the same contents
* there can be multiple deliverables with different version strings
  identifying the same deliverable
* the version of deliverables other than stable is always +1 compared to
  the last release stable.
  The "+1" may mean major, minor, or patch section of version string,
  depending on the contents of changes since last stable release, following
  Semantic versioning 2.0.
*

## Preferences

* the same deliverable is promoted from a "more risky" channel to a less
  risky one without rebuilding. E.g. beta -> stable.

## Calculating the Edge version string

```mermaid

graph TD;

last_stable("Get the last stable version string\nUse that as the base")

are_breaking{"Are there breaking changes?"}
breaking("Bump the Major component of the version")
are_new_things{"Are there new features?"}
minor("Bump the Minor component of the version")
patch("Bump the Patch component of the version")
append_suffix("Compute and add the `-dev` suffix")

START --> last_stable
last_stable --> are_breaking
are_breaking -->|no| are_new_things
are_breaking -->|yes| breaking

are_new_things -->|no| patch
are_new_things -->|yes| minor

breaking --> append_suffix
minor --> append_suffix
patch --> append_suffix
```

## Calculating the Beta version string

```mermaid

graph TD;

last_stable("Get the last edge version string\nUse that as the base")
was_previous{"Is there a beta tag associated\nwith this version?"}
count_betas("Count the number of $VER-beta tags")
suffix("Add `-beta-$COUNT+1`\nE.g. 3.4.5-beta2")
tag("Tag version with the beta version string")
count_try("Count how many `+N` retries have there been")
increase_try("Increase the release try counter\nE.g. 3.4.5-beta2+4")
start_release("Start beta release process")

last_stable --> count_betas
count_betas --> was_previous
was_previous -->|no| suffix
was_previous -->|yes| count_try
count_try --> increase_try
increase_try --> tag
suffix --> tag
tag --> start_release

```

## Edge release pipeline

```mermaid

graph TD;

start("change integrated\nprocess starts")
version("compute the 'edge' version")
build("build of\nsnaps,\ndebs,\ndocker image")
build_decision{"all deliverables available\nbefore the timeout"}

canary("Canary testing")
canary_decision{"Tests passed"}
canary_validated("Move `canary-validated` HEAD\nto the version being CD'd")


start --> version
version --> build
build --> build_decision
build_decision-->|yes| canary
build_decision-->|no| FAIL

canary --> canary_decision
canary_decision-->|yes| canary_validated
canary_decision-->|no| FAIL

canary_validated --> SUCCESS
```
