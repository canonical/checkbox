Validation pipeline execution
=============================

When validating various versions of Checkbox multiple workflows are in play. Everything starts with automated creation of an Edge version.

Creating new Edge version
-------------------------
Every day GitHub checks for new commits that landed in the Checkbox repository,
and if anything new landed a new version is created.


.. mermaid::
    
    graph TB

        A[GitHub Workflow: Detect New Commits]
        C[Mark Version as Edge and Build Snaps]
        E{Did Snap Builds Succeed?}
        F[Upload New Edge Version to Store]
        G[End: Build Failed - No New Edge Version]

        A --> C
        C --> E
        E -->|Yes| F
        E -->|No| G


With new Edge version of Checkbox in the store we can start validating it.

Validating the Edge version
---------------------------

On the Certification Jenkins instance, the ``checkbox-edge-validation-detect-new-build`` job checks the store API for new Edge versions of Checkbox.
The job is defined in the |hwcert-jenkins-jobs|_ repository.

This job is also responsible for checking if all of the necessary snaps were published (for other series and architectures).
Once confirmed, the "Canary Test Plan" is executed. It is defined in the |hwcert-jenkins-jobs|_ repository as too.

.. mermaid::

    graph TB

        A[Detect New Edge Version in Store]
        B{Check if All Necessary Snaps are Published}
        C{Run Canary Test Plan on Devices}
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

        participant Pipeline as Checkbox Validation Pipeline
        participant Jenkins as Jenkins Job
        participant TServer as Testflinger Server
        participant TAgent as Testflinger Agent
        participant Docker as Docker container (Checkbox Controller)
        participant Device as Device Under Test
        participant CAgent as Checkbox Agent
        note over Device,CAgent: Same device

        Pipeline->>Jenkins: Trigger Jenkins Job
        activate Pipeline
        Jenkins->>TServer: Submit Testing Job
        activate TServer
        loop Poll for Job
            TAgent-->>TServer: Check for Available Jobs
        end
        activate TAgent
        TAgent->>Device: Provision Device & Start Checkbox Agent
        activate Device
        activate CAgent
        TAgent->>Docker: Run Checkbox Controller
        activate Docker
        Docker->>CAgent: Start Canary Test Plan
        CAgent-->>Docker: Return Test Results
        deactivate CAgent
        Docker-->>TAgent: Report Results
        deactivate Docker
        TAgent-->>TServer: Job Completion Status
        deactivate TAgent
        TServer-->>Jenkins: Inform Jenkins of Outcome
        deactivate TServer
        Jenkins-->>Pipeline: Update Pipeline with Job Outcome
        deactivate Pipeline

.. add code format to link text
.. |hwcert-jenkins-jobs| replace:: ``hwcert-jenkins-jobs``
.. _hwcert-jenkins-jobs: https://github.com/canonical/hwcert-jenkins-jobs

