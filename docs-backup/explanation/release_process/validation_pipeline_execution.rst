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

On the Certification Jenkins instance, the ``checkbox-edge-validation-detect-new-build`` job checks the store API for new edge versions of Checkbox.
The job is defined in the |hwcert-jenkins-jobs|_ repository.

This job is also responsible for checking if all of the necessary snaps were published (for other series and architectures).
Once confirmed, the "canary test Plan" is executed. It is defined in the |hwcert-jenkins-jobs|_ repository as too.

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
        C -->|Passes| E
        C -->|Fails| D




There are multiple entities participating in the chain of validating a Checkbox snap.

.. mermaid::

    sequenceDiagram

        participant Pipeline as Checkbox validation pipeline
        participant Jenkins as Jenkins job
        participant TServer as Testflinger server
        participant TAgent as Testflinger agent
        participant Docker as Docker container (Checkbox Controller)
        participant Device as Device Under Test
        participant CAgent as Checkbox agent
        note over Device,CAgent: same device

        Pipeline->>Jenkins: Trigger Jenkins job
        activate Pipeline
        Jenkins->>TServer: Submit testing job
        activate TServer
        loop Poll for job
            TAgent-->>TServer: Check for available jobs
        end
        activate TAgent
        TAgent->>Device: Provision device & start Checkbox agent
        activate device
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
        TServer-->>Jenkins: Inform Jenkins of outcome
        deactivate TServer
        Jenkins-->>Pipeline: Update pipeline with job outcome
        deactivate pipeline

.. add code format to link text
.. |hwcert-jenkins-jobs| replace:: ``hwcert-jenkins-jobs``
.. _hwcert-jenkins-jobs: https://github.com/canonical/hwcert-jenkins-jobs

