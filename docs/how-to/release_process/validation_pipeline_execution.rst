Validation pipeline execution
=============================

When validating various versions of Checkbox multiple workflows are in play.
Everything starts with automated creation of an Edge version.

Creating new Edge version
-------------------------
Every day github checks for new commits that landed in the Checkbox repository,
and if anything new landed a new version is created.


.. mermaid::
    
    graph TB

        A[GitHub Workflow: Detect New Commits]

        B[Run Metabox Tests on New Version]
        C[Mark Version as Edge and Build Snaps]
        D{Did Metabox Tests Pass?}
        E{Did Snap Builds Succeed?}
        F[Upload New Edge Version to Store]

        G[End: Build Failed - No New Edge Version]


        A --> B
        B --> D
        D -->|Yes| C
        C --> E
        E -->|Yes| F
        D -->|No| G
        E -->|No| G


With new Edge version of Checkbox in the store we can start validating it.

Validating the Edge version
---------------------------

On the Certification Jenkins instance, the ``{insert_final_job_name_here}`` job checks the store API for new Edge versions of Checkbox.
The job is defined in the |hwcert-jenkins-jobs|_ repository.

This job is also responsible for checking if all of the necessary snaps were published (for other series and architectures).
Once confirmed, the "Canary Test Plan" is defined in `Canary test plan <https://github.com/canonical/checkbox/blob/main/providers/base/units/canary/test-plan.pxu>`_.

.. mermaid::

    graph TB

        A[Detect New Edge Version in Store]
        B{Check if All Necessary Snaps are Published}
        C{Run Canary Test Plan on Devices}
        D[Tag as `edge-validation-failed``]
        E[Tag as `edge-validation-completed``]

        A --> B
        B -->|No| D
        B -->|Yes| C
        C -->|Yes| E
        C -->|No| D




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
.. _hwcert-jenkins-jobs: https://github.com

