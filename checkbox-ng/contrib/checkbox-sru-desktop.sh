#!/bin/bash

function run_test {
    log_file="/var/log/checkbox-`date +%y%m%d-%H%M%S`.log"
    checkbox-cli /usr/bin/checkbox-sru-launcher > $log_file 2>&1
    # The log in temp dir could be a status flag used for CI
    cp $log_file /tmp/checkbox-desktop-sru.log
}


if [ `pidof systemd` ]; then
    # trigger the action if the init process is systemd-based
    systemctl start checkbox-ci-installed-notifier.service
    run_test
    systemctl start checkbox-ci-mailer.service
else
    # trigger the action if the init process is upstart-based (ealier Ubuntu)
    initctl emit checkbox-sru-started
    run_test
    initctl emit checkbox-sru-finished
fi
