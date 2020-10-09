# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import yaml


def decode(assertion_stream):
    """Generate individual assertions in yaml format from a stream.

    Multiple assertions are identified in the stream by a double empty line as
    per the REST API documentation. Signatures are not verified and removed
    so any data returned should be used only for informational purposes.
    """
    count = int(assertion_stream.headers['X-Ubuntu-Assertions-Count'])
    if count > 0:
        # split in to individual assertions
        for assertion in assertion_stream.text.split('\n\n\n\n'):
            # split to remove signature
            content = assertion.split('\n\n')[0]
            if int(yaml.__version__.split('.')[0]) < 5:
                yield yaml.load(content)
            else:
                yield yaml.load(content, Loader=yaml.FullLoader)


def model_to_resource(model_assertion):
    """ Convert assertion yaml to flat dict for resource output."""
    resource = {}
    # list keys that can just be copied over
    wanted_keys = ('type', 'authority-id', 'brand-id', 'model', 'architecture',
                   'base', 'grade', 'sign-key-sha3-384', 'store')
    for key, val in model_assertion.items():
        if key in wanted_keys:
            resource[key] = val
    # handle other more complicated keys
    if 'grade' in model_assertion:
        # is in UC20 format
        resource['grade'] = model_assertion.get('grade')
        for snap in model_assertion['snaps']:
            if snap['type'] in ('kernel', 'gadget'):
                resource[snap['type']] = snap['name']
                resource['{}_track'.format(
                    snap['type'])] = snap['default-channel']
    else:
        # older formats
        for key in ('kernel', 'gadget'):
            val = model_assertion.get(key)
            if val:
                if '=' in val:
                    snap, track = [x.strip() for x in val.split('=')]
                    resource[key] = snap
                    resource['{}_track'.format(key)] = track
                else:
                    resource[key] = val
    return resource


def serial_to_resource(serial_assertion):
    """ Convert assertion yaml to flat dict for resource output."""
    resource = {}
    # list keys that can just be copied over
    wanted_keys = ('type', 'authority-id', 'brand-id', 'model', 'serial',
                   'sign-key-sha3-384')
    for key, val in serial_assertion.items():
        if key in wanted_keys:
            resource[key] = val
    return resource
