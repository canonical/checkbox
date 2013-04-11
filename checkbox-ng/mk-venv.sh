#!/bin/sh
# Create a virtualenv for working with plainbox.
#
# This ensures that 'plainbox' command exists and is in PATH and that the
# plainbox module is correctly located can be imported.
#
# This is how Zygmunt Krynicki works, feel free to use or adjust to your needs

VENV_PATH=
install_missing=0
# Parse arguments:
while [ -n "$1" ]; do
    case "$1" in
        --help|-h)
            echo "Usage: mk-venv.sh [LOCATION]"
            echo ""
            echo "Create a virtualenv for working with plainbox in LOCATION"
            exit 0
            ;;
        --install-missing)
            install_missing=1
            shift
            ;;
        *)
            if [ -z "$VENV_PATH" ]; then
                VENV_PATH="$1"
                shift
            else
                echo "Error: too many arguments: '$1'"
                exit 1
            fi
            ;;
    esac
done

# Apply defaults to arguments without values
if [ -z "$VENV_PATH" ]; then
    # Use sensible defaults for vagrant
    if [ "$LOGNAME" = "vagrant" ]; then
        VENV_PATH=/tmp/venv
    else
        VENV_PATH=/ramdisk/venv
    fi
fi

# Do a sanity check on lsb_release that is missing on Fedora the last time I
# had a look at it.
if [ "x$(which lsb_release)" = "x" ]; then
    echo "This script requires the 'lsb_release' command"
    exit 1
fi

# The code below is a mixture of Debian/Ubuntu packages and pypi packages.
# It is designed to work on Ubuntu 12.04 or later.
# There are _some_ differences between how each release is handled.
#
# Non Ubuntu systems are not tested as they don't have the required checkbox
# package. Debian might be supported once we have JobBox and stuff like Fedora
# would need a whole new approach but patches are welcome [CLA required] 
if [ "$(lsb_release --short --id)" != "Ubuntu" ]; then
    echo "Only Ubuntu is supported by this script."
    echo "If you are interested in using it with your distribution"
    echo "then please join us in #ubuntu-quality on freenode"
    echo
    echo "Alternatively you can use vagrant to develop plainbox"
    echo "on any operating system, even Windows ;-)" 
    echo
    echo "See: http://www.vagrantup.com/ for details"
    exit 1
fi
# From now on we can assume a Debian-like system

# Do some conditional stuff depending on the particular Ubuntu release 
enable_system_site=0
install_coverage=0
install_distribute=0
install_pip=0
# We need:
# python3:
#   because that's what plainbox is written in
# python3-dev
#   because we may pip-install stuff as well and we want to build native extensions
# python3-pkg-resources:
#   because it is used by plainbox to locate files and extension points
# python3-setuptools:
#   because it is used by setup.py 
# python3-lxml:
#   because that's how we validate RealaxNG schemas
# python3-mock:
#   because that's what we used to construct some of our tests
# python3-sphinx:
#   because that's how we build our documentation
# python-virtualenv:
#   because that's how we create the virtualenv to work in
# checkbox:
#   because plainbox depends on it as a job provider 
required_pkgs_base="python3 python3-dev python3-pkg-resources python3-setuptools python3-lxml python3-mock python3-sphinx python-virtualenv checkbox"

# The defaults, install everything from pip and all the base packages
enable_system_site=1
install_distribute=1
install_pip=1
install_coverage=1
install_requests=1
required_pkgs="$required_pkgs_base"

case "$(lsb_release --short --release)" in
    12.04)
        # Ubuntu 12.04, this is the LTS release that we have to support despite
        # any difficulties. It has python3.2 and all of our core dependencies
        # although some packages are old by 13.04 standards, make sure to be
        # careful with testing against older APIs.
        ;;
    12.10)
        ;;
    13.04)
        # On Raring we can use the system package for python3-requests
        install_requests=0
        required_pkgs="$required_pkgs_base python3-requests"
        ;;
    *)
        echo "Using this version of Ubuntu for development is not supported"
        echo "Unsupported version: $(lsb_release --short --release)"
        exit 1
        ;;
esac

# Check if we can create a virtualenv
if [ ! -d $(dirname $VENV_PATH) ]; then
    echo "This script requires $(dirname $VENV_PATH) directory to exist"
    echo "You can use different directory by passing it as argument"
    echo "For a quick temporary location just pass /tmp/venv"
    exit 1
fi

# Check if there's one already there
if [ -d $VENV_PATH ]; then
    echo "$VENV_PATH seems to already exist"
    exit 1
fi

# Ensure that each required package is installed 
for pkg_name in $required_pkgs; do
    # Ensure virtualenv is installed 
    if [ "$(dpkg -s $pkg_name 2>/dev/null | grep '^Status' 2>/dev/null)" != "Status: install ok installed" ]; then
        if [ "$install_missing" -eq 1 ]; then
            echo "Installing required package: $pkg_name"
            sudo apt-get install $pkg_name --yes
        else
            echo "Required package is not installed: '$pkg_name'"
            echo "Either install it manually with:"
            echo "$ sudo apt-get install $pkg_name"
            echo "Or rerun this script with --install-missing"
            exit 1
        fi
    fi
done

# Create a virtualenv
if [ $enable_system_site -eq 1 ]; then
    virtualenv --system-site-packages -p python3 $VENV_PATH
else
    virtualenv -p python3 $VENV_PATH
fi

# Activate it to install additional stuff
. $VENV_PATH/bin/activate

# Install / upgrade distribute
if [ $install_distribute -eq 1 ]; then
    pip install --upgrade https://github.com/checkbox/external-tarballs/raw/master/pypi/coverage-3.6.tar.gz
fi

# Install / upgrade pip
if [ $install_pip -eq 1 ]; then
    pip install --upgrade https://github.com/checkbox/external-tarballs/raw/master/pypi/pip-1.3.1.tar.gz
fi

# Install coverage if required
if [ $install_coverage -eq 1 ]; then
    pip install --upgrade https://github.com/checkbox/external-tarballs/raw/master/pypi/coverage-3.6.tar.gz
fi

# Install requests if required
if [ $install_requests -eq 1 ]; then
    pip install --upgrade https://github.com/checkbox/external-tarballs/raw/master/pypi/requests-1.1.0.tar.gz
fi

# "develop" plainbox
http_proxy=http://127.0.0.1:9/ python3 setup.py develop

echo "To activate your virtualenv run:"
echo "$ . $VENV_PATH/bin/activate"
