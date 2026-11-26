.. _validation_job_example:

Example of a validation job
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The canary workflow fills in the
`tools/lab_dispatch/canary.yaml <https://github.com/canonical/checkbox/blob/main/tools/lab_dispatch/canary.yaml>`_
Testflinger job template for each device. The template uses three variables:

* ``$QUEUE``: the Testflinger queue of the device.
* ``$PROVISION_DATA``: the image to provision, for example
  ``{distro: noble}``.
* ``$CHECKBOX_TRACK``: the Checkbox frontend snap track to install from edge,
  for example ``uc24``.

On the Testflinger agent, the job installs the edge Checkbox snaps on the
device, builds a launcher for the ``com.canonical.certification::canary`` test
plan with the device manifest, and runs it with ``checkbox-cli control``. The
job's test status is the Checkbox exit code.
