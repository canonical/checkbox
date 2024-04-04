#!/bin/bash
set -e
set -x

[ $QUEUE ] || echo "Missing queue" && exit 1
[ $PROVISION_DATA_SOURCE ] || echo "Missing provision data" && exit 1
[ $CHECKBOX_RUNTIME ] || echo "Missing checkbox runtime snap name" && exit 1
[ $CHECKBOX_TRACK ] || echo "Missing frontend snap channel name" && exit 1


cat > job.yaml <<EOF
    job_queue: $QUEUE
    global_timeout: 3600
    output_timeout: 1800
    provision_data:
      $PROVISION_DATA_SOURCE
    test_data:
      test_cmds: |
            #!/bin/bash

            # the machine running this script is the test controller
            # it runs on any device that consumes the jobs on given queue name, for instance "202111-29636"
            # the controller has a 1:1 relationship with the DUT (device under test)
            # to run anything on the DUT, the controller ssh's into the DUT and runs the commands there
            # and then in the end runs checkbox to run the actual testing session
            # the checkbox run is a typical remote session where the machine running this script is the
            # Checkbox Controller and the DUT is the Checkbox Agent

            set -x
            set -e

            # prepare Controller Machine
            sudo add-apt-repository -y ppa:checkbox-dev/edge
            sudo apt-get -qq update
            sudo DEBIAN_FRONTEND=noninteractive apt-get -qq install -y python-cheetah git checkbox-ng

            # get the tools necessary to prepare the target device for testing
            git -C hwcert-jenkins-tools pull -q || (rm -rf hwcert-jenkins-tools && git clone https://github.com/canonical/hwcert-jenkins-tools.git)

            export PATH=\$PATH:hwcert-jenkins-tools/scriptlets

            # install checkbox runtime
            _run_retry sudo snap install $CHECKBOX_RUNTIME --no-wait --channel=latest/edge
            wait_for_snap_complete
            # Let's list all the installed snaps for future debugging ease
            _run snap list

            _run_retry sudo snap install --devmode --channel=$CHECKBOX_TRACK/edge checkbox

            cat <<EOF > canary.launcher
            $(cat canary.launcher)
            EOF

            echo "Installing checkbox in agent container"
            CHECKBOX_VERSION=\$(_run checkbox.checkbox-cli --version)
            git clone --filter=tree:0 https://github.com/canonical/checkbox.git > /dev/null
            hwcert-jenkins-tools/version-published/checkout_to_version.py ~/checkbox "\$CHECKBOX_VERSION"
            (cd checkbox/checkbox-ng; sudo python3 setup.py install > /dev/null)
            sudo rm -rf checkbox

            # run the canary test plan
            PYTHONUNBUFFERED=1 checkbox-cli control \$DEVICE_IP canary.launcher
            EXITCODE=\$?
EOF

cat job.yaml
