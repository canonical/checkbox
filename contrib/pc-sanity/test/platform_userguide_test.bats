#!/usr/bin/env bats

# execute this test file by `bats test/platform_userguide_test`
BIN_FOLDER="contrib/pc-sanity/bin"

function setup() {
    source "$BIN_FOLDER"/platform_userguide_test
}

# A autotest for check_sutton_userguide in bats
@test "test_check_sutton_userguide: Pass if userguide package is installed" {
    set -e
    function dpkg-query() {
        opts="$*"
        if [ -z ${opts##*Package*} ]; then
            echo "oem-sutton-common-doc"
            echo "oem-sutton-foo-doc"
        elif [ -z ${opts##*oem-sutton-foo-doc*} ];then
            echo "install ok installed"
        fi
    }

    run check_sutton_userguide
    [ "$status" -eq 0 ]
}

@test "test_check_sutton_userguide: Error if userguide package is not removed" {
    set -e
    function dpkg-query() {
        opts="$*"
        if [ -z ${opts##*Package*} ]; then
            echo "oem-sutton-common-doc"
            echo "oem-sutton-foo-doc"
        elif [ -z ${opts##*oem-sutton-foo-doc*} ];then
            echo "unknown ok not-installed"
        fi
    }

    run check_sutton_userguide
    [ "$status" -eq 1 ]
}

@test "test_check_sutton_userguide: Error if userguide package is not installed" {
    set -e
    status=0
    function dpkg-query() {
        opts="$*"
        if [ -z ${opts##*Package*} ]; then
            echo ""
        fi
    }

    run check_sutton_userguide
    [ "$status" -eq 1 ]
}
