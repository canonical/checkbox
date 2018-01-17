#!/bin/bash

function run_test {
    log_file="$HOME/checkbox-`date +%y%m%d-%H%M%S`.log"
    log_file_tmp="/tmp/checkbox-sru-desktop.log"
    checkbox-cli /usr/bin/checkbox-sru-launcher > $log_file_tmp 2>&1
    # Lets reserve the log so we could use it to review our tests
    cp $log_file_tmp $log_file
}


if [ `pidof systemd` ]; then
    # trigger the action if the init process is systemd-based
    sudo systemctl start checkbox-ci-installed-notifier.service
    run_test
    sudo systemctl start checkbox-ci-mailer.service
else
    # trigger the action if the init process is upstart-based (ealier Ubuntu)
    sudo initctl emit checkbox-sru-started
    run_test
    sudo initctl emit checkbox-sru-finished
fi
