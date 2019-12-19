#!/usr/bin/env python3

import glob
import os
import subprocess as sp
import sys
import time

import xmlrpc.client


def Chameleon(host, port=9992):
    """
    Get a proxy object that is used to control the Chameleon board.

    The interface definition for this object can be found at:
    https://chromium.googlesource.com/chromiumos/platform/chameleon/+/refs/heads/master/chameleond/interface.py
    """
    print('== Chameleon connection ==')
    print('Target device: {}:{}'.format(host, port))
    proxy = xmlrpc.client.ServerProxy('http://{}:{}'.format(host, port))
    try:
        # test the proxy works
        mac = proxy.GetMacAddress()
        print('MAC address: {}'.format(mac))
    except OSError as e:
        print(e)
        raise SystemExit('ERROR connecting to Chameleon board')
    print()
    return proxy


def get_hdmi_port(chameleon):
    supported_ports = chameleon.GetSupportedPorts()
    for port in supported_ports:
        port_type = chameleon.GetConnectorType(port)
        if port_type == 'HDMI':
            return port


def get_hdmi_status(drm_id):
    path = '/sys/class/drm/{}/status'.format(drm_id)
    with open(path) as sys_f:
        return sys_f.readline().strip()


def get_hdmi_edid(drm_id):
    path = '/sys/class/drm/{}/edid'.format(drm_id)
    output = sp.run(['edid-decode', path], check=False, stdout=sp.PIPE).stdout
    for line in output.decode(sys.stdout.encoding).splitlines():
        if 'Manufacturer:' in line:
            return line.strip()


def edid_from_file(filename):
    with open(filename, 'r') as file:
        if filename.upper().endswith('.TXT'):
            # Convert the EDID text format returned from xrandr.
            hex = file.read().replace('\n', '')
            data = bytes.fromhex(hex)
        else:
            data = open(filename).read()
    return data


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('ERROR: please specify drm card and chameleon IP')

    drm_id = sys.argv[1]
    c = Chameleon(sys.argv[2])

    edid_dir = os.path.expandvars(
        '$PLAINBOX_PROVIDER_DATA/chameleon_edids/daily')
    print('Loading EDIDs from {}'.format(edid_dir))
    edids = glob.glob(edid_dir + os.path.sep + '[A-Z][A-Z][A-Z]_*.txt')

    port_num = get_hdmi_port(c)
    c.Unplug(port_num)

    fails = []
    for edid in edids:
        edid_base = os.path.basename(edid)
        print('=={}=='.format(edid_base))
        print('Send EDID to Chameleon')
        edid_id = c.CreateEdid(edid_from_file(edid))
        c.ApplyEdid(port_num, edid_id)
        print('Plug HDMI')
        c.Plug(port_num)
        time.sleep(2)

        # TODO: make this an actual test
        if get_hdmi_status(drm_id) == 'connected':
            manufacturer_str = get_hdmi_edid(drm_id)
            print(manufacturer_str)
            if edid_base[:3] not in manufacturer_str:
                print('Manufacturer {} not found')
                fails.append(edid_base)
        else:
            print('HDMI not connected')
            fails.append(edid_base)

        print('Unplug HDMI')
        c.Unplug(port_num)
        time.sleep(2)
        print('Free EDID data')
        c.DestroyEdid(edid_id)
        print('====\n', flush=True)

    if fails:
        print("Failed EDIDs:")
        for f in fails:
            print(f)
        raise SystemExit("Total {}/{}".format(len(fails), len(edids)))
    print('PASS')
