# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>
#    Maciej Kisielewski <maciej.kisielewski@canonical.com>

import configparser
import json
import os
import re
import subprocess as sp
import sys


def get_snapctl_config():
    """Query snapctl for config file variables"""
    out = sp.check_output(['snapctl', 'get', 'conf']).decode(
        sys.stdout.encoding).strip()
    if out:
        return json.loads(out)
    return {}


def get_configuration_set():
    """
    Get names and their default values declared in Snap's config_vars.

    config_vars should list all the configuration variables in a `key=value`
    syntax. The line can list variable name only, if the variable should not
    have a default value. All keys should comprise of CAPS, numbers and
    undescores (_).

    The returned keys are lowercase, as required by snapctl.
    """
    config_set_path = os.path.expandvars("$SNAP/config_vars")
    config_set = dict()
    key_re = re.compile(r"^(?:[A-Z0-9]+_?)*[A-Z](?:_?[A-Z0-9])*$")
    try:
        for line in open(config_set_path, 'rt').readlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            k, _, v = line.partition('=')
            if not key_re.match(k):
                raise ValueError("%s is not a valid configuration key" % k)
            # snapd accepts lowercase and dashes only for config names
            # so let's "mangle" the names to match the requirement
            k = k.replace('_', '-').lower()
            config_set[k] = v
    except FileNotFoundError:
        # silently ignore missing config_vars
        pass
    return config_set


def write_checkbox_conf(configuration):
    """Write checkbox.conf in $SNAP_DATA dir."""
    config = configparser.ConfigParser()
    config.optionxform = str
    config.add_section('environment')
    for key in sorted(configuration.keys()):
        val = str(configuration[key])
        # unmangle the key
        key = key.replace('-', '_').upper()
        config.set('environment', key, val)

    checkbox_conf_path = os.path.expandvars("$SNAP_DATA/checkbox.conf")
    os.makedirs(os.path.dirname(checkbox_conf_path), exist_ok=True)
    with open(checkbox_conf_path, 'wt') as stream:
        config.write(stream)


def print_checkbox_conf():
    """Print the current checkbox.conf in $SNAP_DATA."""
    checkbox_conf_path = os.path.expandvars("$SNAP_DATA/checkbox.conf")
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(checkbox_conf_path)
    if config.has_section('environment'):
        for key in config['environment']:
            print('{}={}'.format(key, config['environment'][key]))


def refresh_configuration():
    """
    Read config_vars, write the ones missing in snapd
    and call update configuration in both, snapd and checkbox.conf.

    This is called from the snap configure hook.
    """
    config_vars = get_configuration_set()
    if config_vars:
        current = get_snapctl_config()
        for key in config_vars.keys():
            if key not in current.keys() or not current[key]:
                current[key] = config_vars[key]
        update_configuration(current)


def update_configuration(updated_entries):
    """
    Update snapd configuration and write checkbox.conf file

    The is called from the configure snap app.

    :param updated_entries:
        A dict containing the configuration to set.
        Keys should contain lowercase letters, dashes and number only.
    """
    vars_to_set = []
    key_re = re.compile(r"^(?:[a-z0-9]+-?)*[a-z](?:-?[a-z0-9])*$")
    for k, v in updated_entries.items():
        if not key_re.match(k):
            raise ValueError("'%s' is not a valid key" % k)
        vars_to_set.append('conf.{}={}'.format(
            k.replace('_', '-').lower(), v))
    sp.run(['snapctl', 'set'] + sorted(vars_to_set))
    write_checkbox_conf(get_snapctl_config())
