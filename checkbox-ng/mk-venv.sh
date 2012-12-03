#!/bin/sh
# Create a virtualenv in /ramdisk
#
# This is how Zygmunt Krynicki works, feel free to use or adjust to your needs

VENV_PATH=${1:-/ramdisk/venv}

if [ -z "$(which virtualenv)" ]; then
    echo "You need to install virtualenv to continue"
    echo "On Ubuntu:"
    echo "  sudo apt-get install python-virtualenv"
    exit 1
fi

if [ -z "$(which python3)" ]; then
    echo "You need to install python3 to continue"
    echo "On Ubuntu:"
    echo "  sudo apt-get install python3"
    exit 1
fi

if [ ! -d $(dirname $VENV_PATH) ]; then
    echo "This script requires $(dirname $VENV_PATH) directory to exist"
    echo "You can use different directory by passing it as argument"
    echo "For a quick temporary location just pass /tmp/venv"
    exit 1
fi

if [ ! -d $VENV_PATH ]; then
    virtualenv -p python3 $VENV_PATH
    . $VENV_PATH/bin/activate
    easy_install -U distribute
    easy_install -U coverage
    python3 setup.py develop
else
    echo "$VENV_PATH seems to exist already"
fi

echo "To activate your virtualenv run:"
echo " $ . $VENV_PATH/bin/activate"
