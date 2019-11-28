# Checkbox
## Required packages

To install all dependencies run:

    sudo apt install -yq build-essential intltool lsb-release policykit-1 python3-virtualenv virtualenv python3 python3-distutils-extra python3-jinja2 python3-padme python3-pkg-resources python3-setuptools python3-xlsxwriter python3-pip python3-crypto

## Creating venv

    ./mk-venv
    source venv/bin/activate

## Adding providers to the venv

    /your/provider/directory/manage.py develop -d $PROVIDERPATH
