#!/bin/bash

export ARCH=$(uname -p)
export INSTALL_DIR=/usr/local/checkbox-gfx
export WORKING_DIR=$HOME/.checkbox-gfx-working-dir

sudo mkdir -p $INSTALL_DIR
sudo mkdir -p $WORKING_DIR
sudo chown -R $USER $WORKING_DIR

# Get vendor
if [[ $(lscpu | grep "GenuineIntel") ]]; then
    export VENDOR=Intel
elif [[ $(lscpu | grep "AuthenticAMD") ]]; then
    export VENDOR=AMD
elif [[ $(lscpu | grep "Qualcomm") ]]; then
    export VENDOR=Qualcomm
fi

