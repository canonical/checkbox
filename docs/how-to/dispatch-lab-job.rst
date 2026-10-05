.. _dispatch-lab-job:

Dispatch a Checkbox job in the lab
=====================================

You can use the github workflows to test a repository revision on a
device in the certification lab. It's now supported for both deb and snap jobs:

* ``dispatch_lab_job.yaml``: build and install Checkbox deb packages from
  the selected repository revision.
* ``dispatch_lab_job_with_snaps.yaml``: download a Checkbox runtime snap,
  overlay the selected repository revision's Python packages and providers,
  and install the patched snap on the device.


.. warning::

   The job definitions used by the workflows are a simplified version and they
   don't mimic exactly the ones used in the lab for certification. Use them for
   testing purposes only.


Prerequisites
-------------

You need:

* Access to dispatch workflows in ``canonical/checkbox``.
* The `GitHub CLI <https://cli.github.com/>`_, authenticated with ``gh auth
  login``, or access to the repository's **Actions** tab.
* A lab queue and, if provisioning the device, an image supported by that
  queue. 

The workflows run on a self-hosted runner with access to the lab.

Describe the jobs
-----------------

Pass jobs as a JSON array in ``matrix_to_create``. Each job needs a ``queue``
and a fully qualified ``test_plan`` ID.

Optionally, add ``data_source`` to provision an image and ``match`` to select
tests (see :doc:`using-match`). Without these fields, the workflow uses the
existing image and selects all tests in the plan.

Snap jobs also need ``checkbox_series`` (for example, ``"24"`` for
``checkbox24``) and the device's ``architecture`` (``amd64``, ``arm64``, etc.).
Choose a series compatible with the image.

Replace the example queues and images below with your own. Use separate
device queues for concurrent jobs.

Dispatch a deb job
------------------

Create a file named ``deb-jobs.json``:

.. code-block:: json

   [
     {
       "data_source": "{distro: desktop-22-04-2-uefi}",
       "queue": "202506-36885",
       "test_plan": "com.canonical.certification::smoke",
       "match": ".*smoke/true$"
     }
   ]

This example runs only the base provider's passing smoke test. Dispatch it
with:

.. code-block:: shell

   gh workflow run dispatch_lab_job.yaml \
     --repo canonical/checkbox \
     --ref main \
     -f matrix_to_create="$(cat deb-jobs.json)"

Replace ``main`` with the branch or tag you want to test.

Dispatch a snap job
-------------------

Create a file named ``snap-jobs.json``:

.. code-block:: json

   [
     {
       "data_source": "{distro: noble}",
       "queue": "202012-28526",
       "checkbox_series": "24",
       "architecture": "amd64",
       "test_plan": "com.canonical.certification::smoke",
       "match": ".*smoke/true$"
     }
   ]

Dispatch it with:

.. code-block:: shell

   gh workflow run dispatch_lab_job_with_snaps.yaml \
     --repo canonical/checkbox \
     --ref main \
     -f checkbox_channel=edge \
     -f matrix_to_create="$(cat snap-jobs.json)"

``checkbox_channel`` defaults to ``edge`` and applies to all jobs. The channel
must provide snaps for the requested series and architectures. 

.. Note::

   This workflow tests source changes by patching a store snap, not rebuilding
   them from scratch.

Dispatch from the GitHub UI
------------------------------

1. Open ``canonical/checkbox`` on GitHub and select **Actions**.
2. Select **Dispatch Checkbox jobs in the lab** for debs, or
   **Dispatch Checkbox snap jobs in the lab** for snaps.
3. Click **Run workflow** and select the branch you want to test.
4. Paste a JSON array like the examples above into ``matrix_to_create``.
5. Click **Run workflow** to submit the jobs. Open the new run to follow
   progress and download the submission artifacts when it finishes.

Monitor the run and download the submission
----------------------------------------------

List recent runs of the workflow you dispatched:

.. code-block:: shell

   gh run list --repo canonical/checkbox --workflow dispatch_lab_job.yaml

Use ``dispatch_lab_job_with_snaps.yaml`` instead for snap runs. Then monitor
the desired run using its ID:

.. code-block:: shell

   gh run watch RUN_ID --repo canonical/checkbox

Download ``submission.json`` from the run's **Artifacts** section, or use:

.. code-block:: shell

   gh run download RUN_ID --repo canonical/checkbox --dir submissions


