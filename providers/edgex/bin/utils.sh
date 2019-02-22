#!/bin/bash -e

install_snap()
{
    local the_snap=$1
    local the_channel=$2

    if [ "$the_snap" = "edgexfoundry" ]; then
        snap install $the_snap --channel=$the_channel
    else
        snap install $the_snap --devmode
    fi

}

snap_remove()
{
    snap remove edgexfoundry || true
}
