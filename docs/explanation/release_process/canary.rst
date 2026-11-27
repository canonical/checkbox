.. _canary-explanation:

Canary testing for Checkbox edge version: in-depth process
==========================================================

Introduction
------------

Canary testing applies on Checkbox snaps that are released through the `edge channel <https://snapcraft.io/docs/channels>`_ in the Snap Store. New versions are built daily if changes are made in the code repository.

The following sections provide a detailed walk-through of the canary testing process for the Checkbox Edge version, starting from snap building to the outcomes of the testing.

Snap build and release
-----------------------

Trigger conditions
^^^^^^^^^^^^^^^^^^
The GitHub action responsible for building the snap runs every day. However, it only triggers when the following condition is met:

At least one pull request (PR) has been merged since the last edge build.

Build workflow
^^^^^^^^^^^^^^^

To monitor the build process, or to review the configuration and logs, see
`the GitHub workflow <https://github.com/canonical/checkbox/actions/workflows/daily-builds.yml>`_.

Post-build actions
^^^^^^^^^^^^^^^^^^

Once the build is successful, the snap packages are automatically pushed to the Snap Store in the edge channel. Testers and early adopters can access the latest version through edge releases.

Canary workflow
---------------

When every job of the ``Daily builds`` workflow succeeds on ``main``, including
after its failed jobs are re-run, its last job starts the
`Checkbox edge canary workflow <https://github.com/canonical/checkbox/actions/workflows/checkbox-edge-canary.yml>`_
with its ``promote`` input set. It can also be started manually; a manual run
only moves the ``beta`` branch when its ``promote`` input is set.

For manual runs, the dispatch form lets you override the queue and provision
data of each device independently. The defaults are the devices listed below,
so change only the fields for devices that need to be moved. Provision data
must remain a Testflinger mapping string, for example ``{distro: noble}``.
Automated runs use the configured defaults.

Waiting for the packages
^^^^^^^^^^^^^^^^^^^^^^^^

The workflow reads the Checkbox version in the edge channel of the Snap Store.
If the ``beta`` branch is already at that version, there is nothing to promote,
so a run with ``promote`` set stops there.
Otherwise, the workflow waits up to five hours for all the snaps and Debian
packages of that version to be published.

Testing platforms and specifications
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The workflow runs the canary test plan on three targets in parallel. A target
is an Ubuntu Core track and architecture:

* ``uc22-amd64``: ``hp-elitebook-850-g8-notebook-pc-c28760`` and
  ``hp-elitebook-850-g8-notebook-pc-c28761``.
* ``uc24-amd64``: ``dell-precision-tower-7820-c25401`` and
  ``dell-optiplex-3000-thin-client-c29189``.
* ``uc24-arm64``: ``rpi4`` and ``rpi400-arm64``.

Each device runs the same Testflinger job in its own workflow job, all at the
same time. A target passes if the canary passes on at least one of its
devices. If it fails on all of them, the workflow waits 30 minutes and retries
the devices of that target once.

The :doc:`canary_pipeline` describes the workflow jobs and the
:doc:`validation_job_example` describes the Testflinger job.

For a detailed look on how the job execution is carried out by all the entities in the chain,
refer to the :doc:`validation_pipeline_execution`.

Canary test plan criteria
^^^^^^^^^^^^^^^^^^^^^^^^^

The canary test plan outlines specific tests that are imperative for the new snap's validation. The pipeline's successful conclusion is contingent upon all these tests passing on each of the mentioned platforms.

Outcome and information propagation
-----------------------------------

Should the validation pass on all three targets, the ``beta`` branch in the
Checkbox repository is moved to the revision that got validated, and the beta
release workflow is started to promote the edge packages to beta.

Conclusion
----------

This canary testing process, complete from snap building to testing, ensures that every release of Checkbox in the edge channel is thoroughly vetted and stable.


.. toctree::
   :hidden:

   canary_pipeline
   validation_pipeline_execution
   validation_job_example
