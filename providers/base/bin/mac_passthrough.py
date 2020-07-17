#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Nara Huang <nara.huang@canonical.com>
#
# Script to get system ethernet device MAC address, and from ACPI DSDT table,
# grep "AUXMAC" to get pass-through MAC address,
# then compare them to check if MAC address pass-through function is working
import subprocess
import glob
import os
import shutil
MAC_PASS_SMBIOS_TOKEN = '0x49b'


def get_system_mac():
    """ Get mac addresses from ethernet devices
        Returns:
            List: Mac addresses of ethernet devices
    """
    mac_addresses = []
    for interface in glob.glob("/sys/class/net/en*/address"):
        try:
            with open(interface, 'r') as iface:
                mac = iface.read()
                mac = mac.strip()
                mac = mac.replace(':', '')
                mac_addresses.append(mac)
        except Exception as err:
            raise SystemExit(err)
    return mac_addresses
    # Since system could have multiple ethernet interfaces,
    # the return value is a list.


def get_pass_through_mac():
    """ Get pass-through mac address from BIOS ACPI DSDT table
        iasl command is included in acpica-tools package
        Returns:
            String: Pass-through MAC address from DSDT table
    """
    tmp_path = os.environ.get("SNAP_USER_DATA", "/tmp")
    aml_path = os.path.join(tmp_path, 'dsdt.aml')
    dsl_path = os.path.join(tmp_path, 'dsdt.dsl')
    try:
        shutil.copy('/sys/firmware/acpi/tables/DSDT', aml_path)
        subprocess.call(['iasl', '-d', aml_path], stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT)
        with open(dsl_path, encoding='utf-8', errors='ignore') as dsl:
            dsdt = dsl.readlines()
            for line in dsdt:
                if 'AUXMAC' in line:
                    bios_mac = line.split('#')[1]
                    print('Pass-through MAC address from DSDT table: ' +
                          bios_mac.lower())
                    return bios_mac.lower()
        raise SystemExit('No AUXMAC is found in DSDT table, '
                         'MAC address pass-through is not working.')
    except Exception as err:
        raise SystemExit(err)


def check_mac_passthrough(mac, bios_mac):
    """ Compare pass-through MAC address from BIOS DSDT table
        and system MAC address, to check if the pass-through function works.
        Args:
            mac: A list contains MAC addresses from system
            bios_mac: A string of MAC address from BIOS DSDT table
    """
    if len(mac) == 2 and mac[0] == mac[1]:
        print('AUXMAC in DSDT table is identical to onboard NIC MAC, which '
              'means in BIOS setting, it is set to '
              '"Integrated NIC 1 MAC Address".')
        return 0
    if bios_mac in mac:
        print('AUXMAC in DSDT table is passed to dock, MAC address '
              'pass-through is working.')
        return 0
    else:
        raise SystemExit('MAC address pass-through is not working, '
                         'maybe the dock is not connected?')
    # If a system enables mac pass-through function,
    # but not connected with a dock, it goes here.


def check_smbios_token(index):
    """ Check SMBIOS for BIOS MAC address pass-through setting.
        If it shows "false", then the function is enabled in
        BIOS setting.
        This function requires command "smbios-token-ctl",
        which comes with package "smbios-utils"
        Args:
            index: A string for SMBIOS token index
    """
    smbios_token_cmd = ['smbios-token-ctl', '--token-id=']
    smbios_token_cmd[1] += index
    try:
        out = subprocess.check_output(smbios_token_cmd)
        for line in out.decode("utf-8").splitlines():
            if 'value: bool' in line:
                if 'true' in line:
                    raise SystemExit('MAC address pass-through '
                                     'is disabled in BIOS setting.')
    except Exception as err:
        raise SystemExit(err)
    print('MAC address pass-through is enabled in BIOS setting.')


def main():
    check_smbios_token(MAC_PASS_SMBIOS_TOKEN)
    pasthrough_mac_addresses = get_pass_through_mac()
    os_mac_addresses = get_system_mac()
    check_mac_passthrough(os_mac_addresses, pasthrough_mac_addresses)


if __name__ == '__main__':
    raise SystemExit(main())
