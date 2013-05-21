#!/bin/sh
# Create a virtualenv for working with checkbox-ng.
#
# This ensures that 'checkbox' command exists and is in PATH and that the
# checkbox_ng module is correctly located can be imported.
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
            echo "Create a virtualenv for working with checkbox-ng in LOCATION"
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

# First of all, call mk-venv.sh from plainbox to get 90% of the stuff ready
if [ $install_missing -eq 1 ]; then
    ( cd ../plainbox/ && ./mk-venv.sh "$VENV_PATH" --install-missing ) || exit 1
else
    ( cd ../plainbox/ && ./mk-venv.sh "$VENV_PATH" ) || exit 1
fi

# Activate it to install additional stuff
. "$VENV_PATH/bin/activate"

# "develop" checkbox-ng 
http_proxy=http://127.0.0.1:9/ python3 setup.py develop

echo "To activate your virtualenv run:"
echo "$ . $VENV_PATH/bin/activate"
