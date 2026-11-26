Validation pipeline execution
=============================

When validating various versions of Checkbox multiple workflows are in play. Everything starts with automated creation of an edge version.

Creating new edge version
-------------------------
Every day GitHub checks for new commits that landed in the Checkbox repository,
and if anything new landed a new version is created.


.. mermaid::
    
    graph TB

        A[GitHub workflow: detect new commits]
        C[Mark version as edge and build snaps]
        E{Did snap builds succeed?}
        F[Upload new edge version to store]
        G[End: build failed - no new edge version]

        A --> C
        C --> E
        E -->|Yes| F
        E -->|No| G


With new edge version of Checkbox in the store we can start validating it.

Validating the edge version
---------------------------

When the daily build succeeds, the ``checkbox-edge-canary.yml`` GitHub workflow
reads the new edge version of Checkbox from the store.

It checks that all of the necessary snaps and Debian packages were published
(for other series and architectures). Once confirmed, the canary test plan is
executed on two devices for each platform.

.. mermaid::

    graph TB

        A[Detect new edge version in store]
        B{Check if all necessary snaps are published}
        C{Run canary test plan on devices}
        D[No changes in the repository]
        E[Move `beta` HEAD to the point at the validated revision]

        A --> B
        B -->|No| D
        B -->|Yes| C
        C -->|Passes on every platform| E
        C -->|Fails on both devices of a platform, twice| D




There are multiple entities participating in the chain of validating a Checkbox snap.

.. mermaid::

    sequenceDiagram

        participant Pipeline as Checkbox canary workflow
        participant TServer as Testflinger server
        participant TAgent as Testflinger agent
        participant Docker as Docker container (Checkbox Controller)
        participant Device as Device Under Test
        participant CAgent as Checkbox agent
        note over Device,CAgent: same device

        activate Pipeline
        Pipeline->>TServer: Submit testing job
        activate TServer
        loop Poll for job
            TAgent-->>TServer: Check for available jobs
        end
        activate TAgent
        TAgent->>Device: Provision device & start Checkbox agent
        activate Device
        activate CAgent
        TAgent->>Docker: Run Checkbox controller
        activate Docker
        Docker->>CAgent: Start canary test plan
        CAgent-->>Docker: Return test results
        deactivate CAgent
        Docker-->>TAgent: Report results
        deactivate Docker
        TAgent-->>TServer: Job completion status
        deactivate TAgent
        TServer-->>Pipeline: Inform the workflow of the outcome
        deactivate TServer
        deactivate Pipeline
