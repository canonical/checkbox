.. _canary_pipeline:

Canary pipeline
^^^^^^^^^^^^^^^
The canary pipeline is implemented by the
`checkbox-edge-canary.yml <https://github.com/canonical/checkbox/blob/main/.github/workflows/checkbox-edge-canary.yml>`_
GitHub workflow. It has these jobs:

1. **Wait for the edge packages**: gets the edge version from the Snap Store,
   skips the run if ``beta`` is already at that version, and waits for all the
   snaps and Debian packages of that version to be published.
2. **<platform> on <device>**: one job per device, all running at the same
   time. Each job submits the :doc:`validation_job_example` to its device,
   shows the Testflinger output live, and fails if the setup, provision or
   test phase fails. A failing device does not fail the workflow run. The job
   and the Testflinger artifacts are uploaded as workflow artifacts.
3. **Check if a retry is needed**: lists the platforms that did not pass on
   any device. If there are any, it waits 30 minutes.
4. **<platform> on <device> (retry)**: one retry job per platform. It runs on
   both devices of the platform if the platform did not pass on any device,
   and is skipped otherwise.
5. **Check that every platform passed**: fails if a platform did not pass on
   any device, in either pass.
6. **Move the beta branch**: runs only if the canary passed on all platforms.
   It moves ``beta`` to the validated revision with a deploy key, so the push
   triggers the beta release workflow.
