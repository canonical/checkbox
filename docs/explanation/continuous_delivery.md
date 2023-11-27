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

## Getting to a new beta version

```mermaid

graph TD;

start("change integrated\nprocess starts")
version("compute the 'edge' version")
build("build of\nsnaps,\ndebs,\ndocker image")
build_decision{"all deliverables available\nbefore the timeout"}

canary("Canary testing")
canary_decision{"Tests passed"}
beta_git("Move `beta` HEAD\nto the version being CD'd")
beta_promo("Promote the snaps from edge to beta\ncopy debs from edge ppa to beta ppa")


start --> version
version --> build
build --> build_decision
build_decision-->|yes| canary
build_decision-->|no| FAIL

canary --> canary_decision
canary_decision-->|yes| beta_git
canary_decision-->|no| FAIL

beta_git --> beta_promo

beta_promo --> SUCCESS
```

## Getting a new stable version

```mermaid

graph TD;

start("Stable release automation starts")
check_age{"Was there a beta version older than 2
           weeks, that's newer than the last stable release?"}
up2date("No need for a new stable release")
blocked("Can't do a release")
trim("Trim the version string to X.Y.Z")
ppa("Checkout the repo that corresponds to the checked beta
     and push it to the stable PPA for LP to build")
snaps("Push snaps to the stable channel")
done("Finish")

check_bugs{"Are there any critical bugs that affect
            the chosen beta?"}

start --> check_age
check_age -->|yes| check_bugs
check_age -->|no| up2date

check_bugs --> |yes| blocked
check_bugs --> |no| trim
trim --> ppa
trim --> snaps
ppa --> done
snaps --> done
up2date --> done


```
