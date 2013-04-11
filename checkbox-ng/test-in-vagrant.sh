#!/bin/sh
# Run all tests in various versions of Ubuntu via vagrant

mkdir -p vagrant-logs

test -z $(which vagrant) && echo "You need to install vagrant first" && exit

# When running in tarmac, the state file .vagrant, will be removed when the
# tree is re-pristinized. To work around that, check for present
# VAGRANT_STATE_FILE (custom variable, not set by tarmac or respected by
# vagrant) and symlink the .vagrant state file from there.
if [ "x$VAGRANT_STATE_FILE" != "x" ]; then
    if [ ! -e "$VAGRANT_STATE_FILE" ]; then
        touch "$VAGRANT_STATE_FILE"
    fi
    ln -fs "$VAGRANT_STATE_FILE" .vagrant
fi

outcome=0
# XXX: this list needs to be in sync with plainbox/Vagrantfile
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
    # Remove any old venv we may have
    vagrant ssh $target -c 'rm -rf /tmp/venv/'
    # Test that mk-venv.sh works correctly
    if vagrant ssh $target -c 'cd plainbox && ./mk-venv.sh --install-missing' >vagrant-logs/$target.mk-venv.log 2>vagrant-logs/$target.mk-venv.err; then
        echo "[$target] PlainBox development script (mk-venv.sh): pass"
    else
        outcome=1
        echo "[$target] PlainBox development script (mk-venv.sh): fail"
        echo "[$target] stdout: $(pastebinit vagrant-logs/$target.mk-venv.log)"
        echo "[$target] stderr: $(pastebinit vagrant-logs/$target.mk-venv.err)"
    fi
    # Test that mk-venv.sh produces working environment in which we can run
    # $ plainbox --help
    if vagrant ssh $target -c '. /tmp/venv/bin/activate; plainbox --help' >vagrant-logs/$target.plainbox.log 2>vagrant-logs/$target.plainbox.err; then
        echo "[$target] PlainBox development environment (plainbox --help): pass"
    else
        outcome=1
        echo "[$target] PlainBox development environment (plainbox --help): fail"
        echo "[$target] stdout: $(pastebinit vagrant-logs/$target.plainbox.log)"
        echo "[$target] stderr: $(pastebinit vagrant-logs/$target.plainbox.err)"
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
