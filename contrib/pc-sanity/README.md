# Plainbox Provider for pc sanity

This provider contains test cases and a test plan for pc sanity testing.

It depends on packages from ppa:checkbox-dev/beta in build time.
The launchpad recipe build it daily : https://code.launchpad.net/~oem-solutions-engineers/+recipe/plainbox-provider-pc-sanity-daily-1

## Run autopkgtest to check build time and installation time sanity.

### option 1.
 - build testbed
$ `./autopkgtest.sh build`
 - run autopkgtest against current source.
$ `./autopkgtest.sh`


### options 2. run it by oem-scripts
$ run-autopkgtest lxc focal -C

## Get test case ID that need improvement.
- yq from `wget https://github.com/mikefarah/yq/releases/download/v4.2.1/yq_linux_arm64`
 - $ bin/yq e ".for-all.[]| path| .[-1]" database/jobs-need-improvement.yaml # to get test IDs for all platform.
 - $ bin/yq e ".for-desktop-only.[]| path| .[-1]" database/jobs-need-improvement.yaml # to get test IDs for all platform.
