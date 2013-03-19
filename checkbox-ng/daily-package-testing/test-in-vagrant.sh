#!/bin/sh
# Runs simple smoke tests on the current package in the daily ppa.

mkdir -p vagrant-logs

test -z $(which vagrant) && echo "You need to install vagrant first" && exit

outcome=0
# XXX: this list needs to be in sync with plainbox/daily-pkg-testing/Vagrantfile
target_list="precise quantal raring"
for target in $target_list; do
    # Bring up target if needed
    if ! vagrant status $target | grep -q running; then
        echo "[$target] Bringing VM 'up'"
        if ! vagrant up $target >vagrant-logs/$target.startup.log 2>vagrant-logs/$target.startup.err; then
            outcome=1
            echo "[$target] Unable to 'up' VM!"
            echo "[$target] stdout: $(pastebinit vagrant-logs/$target.startup.log)"
            echo "[$target] stderr: $(pastebinit vagrant-logs/$target.startup.err)"
            echo "[$target] NOTE: unable to execute tests, marked as failed"
            continue
        fi
    fi
    # Display something before the first test output
    echo "[$target] Starting tests..."
    # Test that plainbox --help works correctly
    if vagrant ssh $target -c 'plainbox --help' >vagrant-logs/$target.help.log 2>vagrant-logs/$target.help.err; then
        echo "[$target] packaged PlainBox plainbox --help: pass"
    else
        outcome=1
        echo "[$target] packaged PlainBox plainbox --help: fail"
        echo "[$target] stdout: $(pastebinit vagrant-logs/$target.help.log)"
        echo "[$target] stderr: $(pastebinit vagrant-logs/$target.help.err)"
    fi
    case $VAGRANT_DONE_ACTION in
        suspend)
            # Suspend the target to conserve resources
            echo "[$target] Suspending VM"
            if ! vagrant suspend $target >vagrant-logs/$target.suspend.log 2>vagrant-logs/$target.suspend.err; then
                echo "[$target] Unable to suspend VM!"
                echo "[$target] stdout: $(pastebinit vagrant-logs/$target.suspend.log)"
                echo "[$target] stderr: $(pastebinit vagrant-logs/$target.suspend.err)"
                echo "[$target] You may need to manually 'vagrant destroy $target' to fix this"
            fi
            ;;
        destroy)
            # Destroy the target to work around virtualbox hostsf bug
            echo "[$target] Destroying VM"
            if ! vagrant destroy --force $target >vagrant-logs/$target.destroy.log 2>vagrant-logs/$target.destroy.err; then
                echo "[$target] Unable to destroy VM!"
                echo "[$target] stdout: $(pastebinit vagrant-logs/$target.suspend.log)"
                echo "[$target] stderr: $(pastebinit vagrant-logs/$target.suspend.err)"
                echo "[$target] You may need to manually 'vagrant destroy $target' to fix this"
            fi
            ;;
    esac
done
# Propagate failure code outside
exit $outcome
