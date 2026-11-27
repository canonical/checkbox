.. _canary_pipeline:

Canary pipeline
^^^^^^^^^^^^^^^
The canary pipeline is implemented by the
`checkbox-edge-canary.yml <https://github.com/canonical/checkbox/blob/main/.github/workflows/checkbox-edge-canary.yml>`_
GitHub workflow. It has these jobs:

1. **Wait for the edge packages**: gets the edge version from the Snap Store,
   skips the run if ``beta`` is already at that version, and waits for all the
   snaps and Debian packages of that version to be published.
2. **<target> on <device>**: one job per device, all running at the same
   time. Each job submits the :doc:`validation_job_example` to its device,
   shows the Testflinger output live, and fails if the setup, provision or
   test phase fails. A failing device does not fail the workflow run. The job
   and the Testflinger artifacts are uploaded as workflow artifacts.
3. **Check if a retry is needed**: explains for each target which jobs
   passed, or that no job passed and which devices are retried. If any
   target needs a retry, it waits 30 minutes.
4. **<target> (retry)**: one retry job per target. It runs on both devices
   of the target if no job of that target passed, and is skipped
   otherwise.
5. **Check that every target passed**: accepts the canary only if at least
   one job passed on each target, in either attempt, and lists the passing
   jobs of each target.
6. **Move the beta branch**: runs only if the canary passed on all targets.
   It moves ``beta`` to the validated revision and starts the beta release
   workflow.
