#!/bin/bash

if [ "build" = "$1" ]; then
    autopkgtest-build-lxd images:ubuntu/focal/amd64
else
    autopkgtest -U --setup-commands="sudo apt-get install -y wget snapd software-properties-common &&  add-apt-repository -y -u -s ppa:checkbox-dev/beta && export DEBIAN_FRONTEND=noninteractive"  --shell-fail -- lxd autopkgtest/ubuntu/focal/amd64
fi
