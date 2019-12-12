#!/usr/bin/env python3

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


if __name__ == '__main__':
    drm_id = sys.argv[1]
    c = Chameleon(sys.argv[2])

    start = get_hdmi_status(drm_id)
    print('Starting status: {}'.format(start))
    print(flush=True)

    port_num = get_hdmi_port(c)

    print('chameleon> plug hdmi')
    c.Plug(port_num)
    time.sleep(10)

    new_status = get_hdmi_status(drm_id)
    print('Status after plug request: {}'.format(new_status))
    print(flush=True)
    if new_status != 'connected':
        raise SystemExit('FAIL: hdmi not connected')

    print('chameleon> unplug hdmi')
    c.Unplug(port_num)
    time.sleep(10)

    final_status = get_hdmi_status(drm_id)
    print('Status after unplug request: {}'.format(final_status))
    print(flush=True)
    if final_status != 'disconnected':
        raise SystemExit('FAIL: hdmi did not disconnect')

    print('PASS')
