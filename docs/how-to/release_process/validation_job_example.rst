.. _validation_job_example:

Example of a validation job
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Below is the shell code that can be used as a build step in Jenkins in a job
responsible for validating edge snap of Checkbox.

::

  #!/bin/bash
  set -e
  set -x

  cat > job.yaml <<EOF
      job_queue: dearest-team
      global_timeout: 3600
      output_timeout: 1800
      provision_data:
        distro: core22-latest
      test_data:
        test_cmds: |
              #!/bin/bash

              # the machine running this script is the test controller
              # it runs on any device that consumes the jobs on given queue name, for instance "dearest-team"
              # the controller has a 1:1 relationship with the DUT (device under test)
              # to run anything on the DUT, the controller ssh's into the DUT and runs the commands there
              # and then in the end runs checkbox to run the actual testing session
              # the checkbox run is a typical remote session where the machine running this script is the
              # Checkbox Controller and the DUT is the Checkbox Agent

              set -x
              set -e

              # prepare Controller Machine
              sudo add-apt-repository ppa:checkbox-dev/ppa -y
              sudo apt-get -qq update
              sudo DEBIAN_FRONTEND=noninteractive apt-get -qq install -y python-cheetah git checkbox-ng

              # get the tools necessary to prepare the target device for testing
              git clone -b snap-update-tools https://github.com/kissiel/hwcert-jenkins-tools.git
              export PATH=$PATH:hwcert-jenkins-tools/scriptlets

              # install checkbox
              _run_retry sudo snap install checkbox22 --no-wait --channel=latest/edge 
              wait_for_snap_complete
              # Let's list all the installed snaps for future debugging ease
              _run snap list

              _run_retry sudo snap install --devmode --channel=uc22/edge checkbox

              # run the canary test plan
              PYTHONUNBUFFERED=1 checkbox-cli remote \$DEVICE_IP hwcert-jenkins-tools/snap-update-tools/canary.launcher
              EXITCODE=\$?
  EOF

  JOB_ID=$(testflinger submit -q job.yaml)
  echo "JOB_ID: $JOB_ID"
  echo "$JOB_ID" > JOB_ID
  testflinger poll $JOB_ID

  TEST_STATUS=$(testflinger results $JOB_ID |jq -r .test_status)

  echo "Test exit status: $TEST_STATUS"
  exit $EXITCODE
