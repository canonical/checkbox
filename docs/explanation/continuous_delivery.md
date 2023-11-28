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
