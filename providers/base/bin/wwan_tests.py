#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Po-Hsu Lin <po-hsu.lin@canonical.com>

import argparse
import logging
import os
import subprocess
import sys
import time

import dbus


TEST_IP = "8.8.8.8"
GSM_CON_ID = "GSMCONN"


DBUS_PROPERTIES = 'org.freedesktop.DBus.Properties'
DBUS_OBJECTMANAGER = 'org.freedesktop.DBus.ObjectManager'

DBUS_MM1_SERVICE = 'org.freedesktop.ModemManager1'
DBUS_MM1_PATH = '/org/freedesktop/ModemManager1'
DBUS_MM1_IF = 'org.freedesktop.ModemManager1'
DBUS_MM1_IF_MODEM = 'org.freedesktop.ModemManager1.Modem'
DBUS_MM1_IF_MODEM_SIMPLE = 'org.freedesktop.ModemManager1.Modem.Simple'
DBUS_MM1_IF_MODEM_3GPP = 'org.freedesktop.ModemManager1.Modem.Modem3gpp'
DBUS_MM1_IF_MODEM_CDMA = 'org.freedesktop.ModemManager1.Modem.ModemCdma'
DBUS_MM1_IF_SIM = 'org.freedesktop.ModemManager1.Sim'

MMModemCapability = {
    'MM_MODEM_CAPABILITY_NONE': 0,
    'MM_MODEM_CAPABILITY_POTS': 1 << 0,
    'MM_MODEM_CAPABILITY_CDMA_EVDO': 1 << 1,
    'MM_MODEM_CAPABILITY_GSM_UMTS': 1 << 2,
    'MM_MODEM_CAPABILITY_LTE': 1 << 3,
    'MM_MODEM_CAPABILITY_LTE_ADVANCED': 1 << 4,
    'MM_MODEM_CAPABILITY_IRIDIUM': 1 << 5,
    'MM_MODEM_CAPABILITY_ANY': 0xFFFFFFFF}


class MMDbus():
    def __init__(self):
        self._bus = dbus.SystemBus()
        self._modems = []
        try:
            manager_proxy = self._bus.get_object(DBUS_MM1_SERVICE,
                                                 DBUS_MM1_PATH)
            om = dbus.Interface(manager_proxy, DBUS_OBJECTMANAGER)
            self._modems = om.GetManagedObjects()
        except dbus.exceptions.DBusException as excp:
            if (excp.get_dbus_name() ==
                    "org.freedesktop.DBus.Error.ServiceUnknown"):
                logging.error(excp.get_dbus_message())
                logging.error(
                    "Note: wwan_tests.py requires ModemManager >=1.0")
            else:
                logging.error(excp.get_dbus_message())
            return

    def _modem_by_id(self, mm_id):
        for m in self._modems:
            if mm_id == (int(os.path.basename(m))):
                return m

    def _modem_props_iface(self, mm_id):
        m = self._modem_by_id(mm_id)
        if m is not None:
            proxy = self._bus.get_object(DBUS_MM1_SERVICE, m)
            return dbus.Interface(proxy, dbus_interface=DBUS_PROPERTIES)

    def get_modem_ids(self):
        modem_ids = []
        for m in self._modems:
            modem_ids.append((int(os.path.basename(m))))
        return modem_ids

    def equipment_id_to_mm_id(self, equipment_id):
        for mm_id in self.get_modem_ids():
            if equipment_id == self.get_equipment_id(mm_id):
                return mm_id

    def get_rat_support(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        return pi.Get(DBUS_MM1_IF_MODEM, 'CurrentCapabilities')

    def get_equipment_id(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        return pi.Get(DBUS_MM1_IF_MODEM, "EquipmentIdentifier")

    def get_manufacturer(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        return pi.Get(DBUS_MM1_IF_MODEM, 'Manufacturer')

    def get_model_name(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        return pi.Get(DBUS_MM1_IF_MODEM, 'Model')

    def sim_present(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        if pi.Get(DBUS_MM1_IF_MODEM, 'Sim') != '/':
            return True
        return False

    def _get_sim_pi(self, mm_id):
        pi = self._modem_props_iface(mm_id)
        sim_path = pi.Get(DBUS_MM1_IF_MODEM, 'Sim')
        if sim_path != '/':
            sim_proxy = self._bus.get_object(DBUS_MM1_SERVICE, sim_path)
            return dbus.Interface(sim_proxy, dbus_interface=DBUS_PROPERTIES)

    def get_sim_operatorname(self, mm_id):
        sim_pi = self._get_sim_pi(mm_id)
        if sim_pi is None:
            return 'No card'
        return sim_pi.Get(DBUS_MM1_IF_SIM, 'OperatorName')

    def get_sim_operatoridentifier(self, mm_id):
        sim_pi = self._get_sim_pi(mm_id)
        if sim_pi is None:
            return 'No card'
        return sim_pi.Get(DBUS_MM1_IF_SIM, 'OperatorIdentifier')

    def get_sim_imsi(self, mm_id):
        sim_pi = self._get_sim_pi(mm_id)
        if sim_pi is None:
            return 'No card'
        return sim_pi.Get(DBUS_MM1_IF_SIM, 'Imsi')

    def get_sim_simidentifier(self, mm_id):
        sim_pi = self._get_sim_pi(mm_id)
        if sim_pi is None:
            return 'No card'
        return sim_pi.Get(DBUS_MM1_IF_SIM, 'SimIdentifier')


def _value_from_table(item, item_id, key):
    if item == 'modem':
        flag = '-m'
    if item == 'sim':
        flag = '-i'
    proc = subprocess.Popen(['mmcli', flag, str(item_id)],
                            stdout=subprocess.PIPE)
    while True:
        line = proc.stdout.readline().decode(sys.stdout.encoding)
        if line == '':
            break
        if key in line:
            chars = ' |\'\n\t'
            for c in chars:
                if c in line:
                    line = line.replace(c, '')
            value = line.split(':', 1)[1]
            return value


class MMCLI():
    def __init__(self):
        self._modem_ids = []
        try:
            proc = subprocess.Popen(['mmcli', '-L'],
                                    stdout=subprocess.PIPE)
            while True:
                line = proc.stdout.readline().decode(sys.stdout.encoding)
                if line == '':
                    break
                if '/org/freedesktop/ModemManager1/Modem' in line:
                    path = line.strip().split()[0]
                    self._modem_ids.append(int(os.path.basename(path)))
        except OSError:
            logging.error("mmcli not found")

    def _get_sim_id(self, mm_id):
        sim_value = _value_from_table('modem', mm_id, 'SIM')
        if sim_value == 'none':
            return None
        else:
            return int(os.path.basename(sim_value))

    def get_modem_ids(self):
        return self._modem_ids

    def equipment_id_to_mm_id(self, equipment_id):
        for mm_id in self.get_modem_ids():
            if equipment_id == self.get_equipment_id(mm_id):
                return mm_id

    def get_equipment_id(self, mm_id):
        return _value_from_table('modem', mm_id, 'equipment id')

    def get_manufacturer(self, mm_id):
        return _value_from_table('modem', mm_id, 'manufacturer')

    def get_model_name(self, mm_id):
        return _value_from_table('modem', mm_id, 'model')

    def sim_present(self, mm_id):
        if self._get_sim_id(mm_id) is None:
            return False
        return True

    def get_sim_operatorname(self, mm_id):
        sim_id = self._get_sim_id(mm_id)
        if sim_id is None:
            return 'No card'
        return _value_from_table('sim', sim_id, 'operator name')

    def get_sim_imsi(self, mm_id):
        sim_id = self._get_sim_id(mm_id)
        if sim_id is None:
            return 'No card'
        return _value_from_table('sim', sim_id, 'imsi')

    def get_sim_operatoridentifier(self, mm_id):
        sim_id = self._get_sim_id(mm_id)
        if sim_id is None:
            return 'No card'
        return _value_from_table('sim', sim_id, 'operator id')

    def get_sim_simidentifier(self, mm_id):
        sim_id = self._get_sim_id(mm_id)
        if sim_id is None:
            return 'No card'
        return _value_from_table('sim', sim_id, '   id')


def _create_3gpp_connection(wwan_if, apn):
    subprocess.check_call(["nmcli", "c", "add",
                           "con-name", GSM_CON_ID,
                           "type", "gsm",
                           "ifname", wwan_if,
                           "apn", apn])


def _wwan_radio_on():
    subprocess.check_call(["nmcli", "r", "wwan", "on"])


def _wwan_radio_off():
    subprocess.check_call(["nmcli", "r", "wwan", "off"])


def _destroy_3gpp_connection():
    subprocess.check_call(["nmcli", "c",
                           "delete", GSM_CON_ID])


def _ping_test(if_name):
    ret_code = 1
    route = subprocess.call(["ip", "route", "add", TEST_IP, "dev", if_name])
    if route == 0:
        ret_code = subprocess.check_call(["ping", "-c", "4",
                                          "-I", if_name, TEST_IP])
        subprocess.call(["ip", "route", "del", TEST_IP, "dev", if_name])
    return ret_code


class ThreeGppConnection():

    def invoked(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('wwan_control_if',  type=str,
                            help='The control interface for the device')
        parser.add_argument('wwan_net_if', type=str,
                            help='The network interface used when connected')
        parser.add_argument('apn', type=str,
                            help='The APN for data connection')
        parser.add_argument('wwan_setup_time', type=int, default=30,
                            help='delay before ping test')
        args = parser.parse_args(sys.argv[2:])
        ret_code = 1
        try:
            _create_3gpp_connection(args.wwan_control_if, args.apn)
            _wwan_radio_on()
            time.sleep(args.wwan_setup_time)
            ret_code = _ping_test(args.wwan_net_if)
        except subprocess.SubprocessError:
            pass
        _destroy_3gpp_connection()
        _wwan_radio_off()
        sys.exit(ret_code)


class CountModems():

    def invoked(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--use-cli', action='store_true',
                            help="Use mmcli for all calls rather than dbus")
        args = parser.parse_args(sys.argv[2:])
        if args.use_cli:
            mm = MMCLI()
        else:
            mm = MMDbus()
        print(len(mm.get_modem_ids()))


class Resources():

    def invoked(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--use-cli', action='store_true',
                            help="Use mmcli for all calls rather than dbus")
        args = parser.parse_args(sys.argv[2:])
        if args.use_cli:
            mm = MMCLI()
        else:
            mm = MMDbus()
        for m in mm.get_modem_ids():
            print("mm_id: {}".format(m))
            print("hw_id: {}".format(mm.get_equipment_id(m)))
            print("manufacturer: {}".format(mm.get_manufacturer(m)))
            print("model: {}".format(mm.get_model_name(m)))
            print()


class SimPresent():

    def invoked(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('hw_id',  type=str,
                            help='The hardware ID of the modem whose attached'
                            'SIM we want to query')
        parser.add_argument('--use-cli', action='store_true',
                            help="Use mmcli for all calls rather than dbus")
        args = parser.parse_args(sys.argv[2:])
        if args.use_cli:
            mm = MMCLI()
        else:
            mm = MMDbus()
        mm_id = mm.equipment_id_to_mm_id(args.hw_id)
        if not mm.sim_present(mm_id):
            sys.exit(1)


class SimInfo():

    def invoked(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('hw_id',  type=str,
                            help='The hardware ID of the modem whose attached'
                            'SIM we want to query')
        parser.add_argument('--use-cli', action='store_true',
                            help="Use mmcli for all calls rather than dbus")
        args = parser.parse_args(sys.argv[2:])
        if args.use_cli:
            mm = MMCLI()
        else:
            mm = MMDbus()
        mm_id = mm.equipment_id_to_mm_id(args.hw_id)
        print("Operator: {}".format(mm.get_sim_operatorname(mm_id)))
        print("IMSI: {}".format(mm.get_sim_imsi(mm_id)))
        print("MCC/MNC: {}".format(mm.get_sim_operatoridentifier(mm_id)))
        print("ICCID: {}".format(mm.get_sim_simidentifier(mm_id)))


class WWANTests():

    def main(self):
        sub_commands = {
            'count': CountModems,
            'resources': Resources,
            '3gpp-connection': ThreeGppConnection,
            'sim-present': SimPresent,
            'sim-info': SimInfo
        }
        parser = argparse.ArgumentParser()
        parser.add_argument('subcommand', type=str, choices=sub_commands)
        args = parser.parse_args(sys.argv[1:2])
        sub_commands[args.subcommand]().invoked()


if __name__ == "__main__":
    WWANTests().main()
