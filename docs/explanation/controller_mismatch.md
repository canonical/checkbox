# The controller mismatch problem

## IMPORTANT DISCLAIMER

THE DIAGRAMS DRAWN HERE DO NOT DESCRIBE GIT HISTORY

THEY DESCRIBE INTERACTION BETWEEN ENTITIES IN A CHRONOLOGICAL ORDER

## Current state

We keep a reusable controller docker image that gets updated manually.
We are **guaranteed** to be out of sync every time a new major version is released.

### Happy case

The controller in the docker image is fresh enough to control the agent.

```mermaid
---
title: "'beta' means channel of distribution (snap store / PPA)"
---

%%{init: { 'gitGraph': {'mainBranchName': 'beta'}}}%%


gitGraph LR:

   commit id:"1.0.0"
   branch reusable-docker-image order:3
   commit id:"Save"
   checkout beta
   commit id:"1.0.1"
   branch DUT

   commit id:"provision"
   commit id:"agent 1.0.1 running"

   checkout beta
   commit id:"1.0.2"

   checkout reusable-docker-image
   branch controller

   commit id:"provisions with 1.0.0"
   commit id:"controller 1.0.0" tag: "can control 1.0.1"

   checkout DUT
   commit type:REVERSE id:"finish"

   checkout beta

   commit id:"1.1.1"
   commit id:"2.0.0"
```

### Unhappy case

The controller in the docker image is stale and cannot control the agent.

```mermaid
---
title: "'beta' means channel of distribution (snap store / PPA)"
---

%%{init: { 'gitGraph': {'mainBranchName': 'beta'}}}%%


gitGraph LR:

   commit id:"1.0.0"
   branch reusable-docker-image order:3
   commit id:"Save"
   checkout beta
   commit id:"1.0.1"
   commit id:"1.1.1"
   commit id:"2.0.0"
   branch DUT

   commit id:"provision"
   commit id:"agent 2.0.0 running"

   checkout beta

   checkout reusable-docker-image
   branch controller

   commit id:"provisions with 1.0.0"
   commit type: HIGHLIGHT id:"controller 1.0.0" tag: "cannot control 2.0.0"

   checkout DUT
   commit type:REVERSE id:"finish"


   checkout beta
   commit id:"2.0.1"

   checkout reusable-docker-image
   merge beta id:"update the container"

   checkout beta

   commit id:"2.1.0"

```

## proposed solution 1: provisioning controler ad hoc (rejected)

The controller is being provisioned when the testing commences using the same channel
as the one that was used on the DUT. This creates a window where a race condition can
occur in which a breaking change may have been released. And because the installation
of Checkbox on DUT and controller is not atomic, they can be mismatched.

### happy case

```mermaid
---
title: "'beta' means channel of distribution (snap store / PPA)"
---

%%{init: { 'gitGraph': {'mainBranchName': 'beta'}}}%%

gitGraph LR:

   commit id:"1.0.0"
   commit id:"1.0.1"
   branch DUT

   commit id:"provision"
   commit id:"agent 1.0.1 running"

   checkout beta
   commit id:"1.0.2"

   branch controller

   commit id:"provisions with 1.0.2"
   commit id:"controller 1.0.2" tag: "can control 1.0.1"

   checkout DUT
   commit type:REVERSE id:"finish"

   checkout beta

   commit id:"1.1.1"
   commit id:"2.0.0"
```

### unhappy case

```mermaid
---
title: "'beta' means channel of distribution (snap store / PPA)"
---

%%{init: { 'gitGraph': {'mainBranchName': 'beta'}}}%%

gitGraph LR:

   commit id:"1.0.0"
   commit id:"1.0.1"
   branch DUT

   commit id:"provision"
   commit id:"agent 1.0.1 running"

   checkout beta
   commit id:"1.0.2"
   commit id:"2.0.0"

   branch controller

   commit type: HIGHLIGHT id:"provisions with 2.0.0"
   commit id:"controller 2.0.0" tag: "cannot control 1.0.1"

   checkout DUT
   commit type:REVERSE id:"finish"

   checkout beta

   commit id:"2.0.1"
   commit id:"2.1.0"

```

## Proposed solution with versioned docker images

The controller image used always corresponds to the version installed on the DUT.
Same version of both ends means no opportunity for a mismatch.

```mermaid
---
title: "'beta' means channel of distribution (snap store / PPA)"
---

%%{init: { 'gitGraph': {'mainBranchName': 'beta'}}}%%

gitGraph LR:
   commit id:"1.0.0"

   branch checkbox-docker
   checkout beta
   commit id:"1.0.1"
   checkout checkbox-docker
   merge beta id:"update to 1.0.1"
   branch controller order:2
   checkout beta
   branch DUT order:1

   commit id:"provision"
   commit id:"agent 1.0.1 running"

   checkout beta
   commit id:"1.0.2"
   checkout checkbox-docker
   merge beta id:"update to 1.0.2"
   checkout beta
   commit id:"2.0.0"
   checkout checkbox-docker
   merge beta id:"update to 2.0.0"
   checkout beta


   checkout controller

   commit id:"provisions to DUT's version"
   commit id:"controller 1.0.1" tag: "can control 1.0.1"

   checkout DUT
   commit type:REVERSE id:"finish"

   checkout beta

   commit id:"2.0.1"
   checkout checkbox-docker
   merge beta id:"update to 2.0.1"
   checkout beta
   commit id:"2.1.0"
   checkout checkbox-docker
   merge beta id:"update to 2.1.0"
   checkout beta

```
