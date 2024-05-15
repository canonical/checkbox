#!/usr/bin/env bats

# execute this test file by `bats test/platform_meta_test`
BIN_FOLDER="contrib/pc-sanity/bin"

function setup() {
    # shellcheck source=/dev/null
    source "$BIN_FOLDER"/platform_meta_test
}

function ubuntu-drivers() {
    echo "$ubuntu_drivers_string"
}

function lsb_release() {
    echo "$ubuntu_codename"
}

@test "somerville in focal/jammy : Pass if meta package installed" {
    set -e
    for ubuntu_codename in 'focal' 'jammy'; do
        BIOSID='08AF'
        ubuntu_drivers_string="oem-somerville-beric-icl-meta"
        function dpkg() {
            echo "$dpkg_string"
        }
        function apt-cache() {
           echo "Modaliases: meta(pci:*sv00001028sd0000$BIOSID*)"
        }
        function dpkg-query() {
            opts="$@"
            if [ -z ${opts##*oem-somerville-beric-icl-meta*} ]; then
                echo "install ok installed"
            elif [ -z ${opts##*oem-somerville-factory-beric-icl-meta*} ];then
                echo "install ok installed"
            fi
        }
        dpkg_string="
        ii  oem-somerville-beric-icl-meta                 20.04ubuntu3.1                              all          hardware support for Somerville beric-icl platform
        ii  oem-somerville-factory-beric-icl-meta         20.04ubuntu3.1                              all          hardware support for Somerville beric-icl platform
        "
        run check_somerville_meta
        [ "$status" -eq 0 ]
    done
}

@test "somerville in focal/jammy : Error if meta package in remove candidate state" {
    set -e
    for ubuntu_codename in 'focal' 'jammy'; do
        BIOSID='08AF'
        ubuntu_drivers_string="oem-somerville-beric-icl-meta"
        function dpkg() {
            echo "$dpkg_string"
        }
        function apt-cache() {
           echo "Modaliases: meta(pci:*sv00001028sd0000$BIOSID*)"
        }
        function dpkg-query() {
            # the message when `dpkg-query -W -f='${Status}\n' "$package_in_rc_state"`
            opts="$@"
            if [ -z ${opts##*oem-somerville-beric-icl-meta*} ]; then
                echo "deinstall ok config-files"
            elif [ -z ${opts##*oem-somerville-factory-beric-icl-meta*} ];then
                echo "deinstall ok config-files"
            fi
        }
        dpkg_string="
        ii  oem-somerville-beric-icl-meta                 20.04ubuntu3.1                              all          hardware support for Somerville Bulbasaur platform
        "
        run check_somerville_meta
        [ "$status" -eq 1 ]
    done
}

# For the case that meta package not installed.
@test "somerville in focal/jammy : Error if meta package Not installed" {
    set -e
    for ubuntu_codename in 'focal' 'jammy'; do
        BIOSID='08AF'
        ubuntu_drivers_string="oem-somerville-beric-icl-meta"
        function dpkg() {
            echo "$dpkg_string"
        }
        function apt-cache() {
           echo "Modaliases: meta(pci:*sv00001028sd0000$BIOSID*)"
        }
        function dpkg-query() {
            opts="$@"
            if [ -z ${opts##*oem-somerville-beric-icl-meta*} ]; then
                # the message when `dpkg-query -W -f='${Status}\n' "$package_not_installed"`
                echo "dpkg-query: no packages found matching "
            elif [ -z ${opts##*oem-somerville-factory-beric-icl-meta*} ];then
                echo "dpkg-query: no packages found matching "
            fi
        }
        dpkg_string="
        ii  oem-ouagadougou-meta                          1.0~20.04ouagadougou4                          all          Meta package for the OEM mainstreams image.
        ii  oem-somerville-factory-meta                   20.04ubuntu9                                   all          hardware support for Somerville platform
        ii  oem-somerville-meta                           20.04ubuntu9                                   all          hardware support for Somerville platform
        ii  python3-importlib-metadata                    1.5.0-1                                        all          library to access the metadata for a Python package - Python 3.x
        "
        run check_somerville_meta
        [ "$status" -eq 1 ]
    done
}

@test "somerville in focal/jammy : Error if factory meta package Not installed" {
    set -e
    for ubuntu_codename in 'focal' 'jammy'; do
        BIOSID='08AF'
        ubuntu_drivers_string="oem-somerville-beric-icl-meta"
        function dpkg() {
            echo "$dpkg_string"
        }
        function apt-cache() {
           echo "Modaliases: meta(pci:*sv00001028sd0000$BIOSID*)"
        }
        function dpkg-query() {
            opts="$@"
            if [ -z ${opts##*oem-somerville-beric-icl-meta*} ]; then
                echo "install ok installed"
            elif [ -z ${opts##*oem-somerville-factory-beric-icl-meta*} ];then
                echo "dpkg-query: no packages found matching "
            fi
        }
        dpkg_string="
        ii  oem-ouagadougou-meta                          1.0~20.04ouagadougou4                          all          Meta package for the OEM mainstreams image.
        ii  oem-somerville-factory-meta                   20.04ubuntu9                                   all          hardware support for Somerville platform
        ii  oem-somerville-meta                           20.04ubuntu9                                   all          hardware support for Somerville platform
        ii  python3-importlib-metadata                    1.5.0-1                                        all          library to access the metadata for a Python package - Python 3.x
        "
        run check_somerville_meta
        [ "$status" -eq 1 ]
    done
}
