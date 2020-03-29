#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Adrian Lane <adrian.lane@canonical.com>

import subprocess
import re
import os
import time


def main():
    # globals
    # using relative paths
    start_time = time.clock()
    path_lsmod = 'lsmod'
    path_modprobe = 'modprobe'
    kernel_modules = (
        'ipmi_si',
        'ipmi_devintf',
        'ipmi_powernv',
        'ipmi_ssif',
        'ipmi_msghandler')
    path_ipmi_chassis = 'ipmi-chassis'
    path_ipmi_config = 'ipmi-config'
    path_bmc_info = 'bmc-info'
    path_ipmi_locate = 'ipmi-locate'

    print ('Running IPMI tests...')
    # check kernel modules
    kernel_mods(path_lsmod, path_modprobe, kernel_modules)
    # tally results
    results = []
    results.append(impi_chassis(path_ipmi_chassis))
    results.append(pwr_status(path_ipmi_chassis))
    results.append(ipmi_channel(path_ipmi_config))
    results.append(bmc_info(path_bmc_info))
    results.append(ipmi_version(path_bmc_info))
    results.append(ipmi_locate(path_ipmi_locate))

    if sum(results) > 0:
        end_time = time.clock()
        total_time = "{0:.4f}".format(end_time - start_time)
        print ('-----------------------')
        print ('## IPMI tests failed! ##')
        print (
            f'## Chassis: {results[0]}  Power: {results[1]}  '
            f'Channel: {results[2]}  BMC: {results[3]}  '
            f'IPMI Version: {results[4]}  IPMI Locate: {results[5]} ##')
        print (f'## Total time: {total_time}s ##')
    else:
        end_time = time.clock()
        total_time = "{0:.4f}".format(end_time - start_time)
        print ('-----------------------')
        print ('## IPMI tests passed! ##')
        print (f'## Total time: {total_time}s ##')


def kernel_mods(path_lsmod, path_modprobe, kernel_modules):
    print('-----------------------')
    print ('Verifying kernel modules:')
    try:
        process = subprocess.Popen(
            [path_lsmod],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate(timeout=15)
        for module in kernel_modules:
            if module in output.decode('utf-8'):
                print (f'- {module} already loaded.')
            else:
                try:
                    subprocess.check_call(
                        [path_modprobe, module],
                        stderr=subprocess.PIPE, timeout=15)
                    print (f'- Successfully loaded module {module}')
                except subprocess.TimeoutExpired:
                    print (f'Timeout ({e.timeout}s) calling modprobe!')
                except subprocess.CalledProcessError:
                    print ('  *******************************************')
                    print (f'  WARNING: Unable to load module {module}')
                    print ('  Continuing run, but in-band IPMI may fail')
                    print ('  *******************************************')
                except EnvironmentError:
                    print ('Unable to invoke modprobe!\n')
        print ('')
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) calling lsmod!')
    except subprocess.SubprocessError:
        # fail if true?
        print ('Error calling lsmod!\n')
    except EnvironmentError:
        # fail if true?
        print ('Unable to invoke lsmod!\n')


def impi_chassis(path_ipmi_chassis):
    print('-----------------------')
    print('Fetching chassis status:')
    start_time = time.clock()
    try:
        fnull = open(os.devnull, 'w')
        subprocess.check_call(
            [path_ipmi_chassis, '--get-status'],
            stdout=fnull, stderr=subprocess.PIPE, timeout=15)
        end_time = time.clock()
        total_time = "{0:.4f}".format(end_time - start_time)
        print('Successfully fetched chassis status!')
        print (f'(took {total_time}s)\n')
        return 0
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) fetching chassis status!\n')
        return 1
    except subprocess.CalledProcessError:
        print ('Error calling ipmi_chassis() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke ipmi-chassis!\n')
        return 1


def pwr_status(path_ipmi_chassis):
    print('-----------------------')
    print('Fetching power status:')
    start_time = time.clock()
    regex = re.compile('^System Power')
    try:
        process = subprocess.Popen(
            [path_ipmi_chassis, '--get-status'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate(timeout=15)
        output = output.decode('utf-8')
        for line in output.rstrip().split('\n'):
            if re.search(regex, line):
                end_time = time.clock()
                total_time = "{0:.4f}".format(end_time - start_time)
                print ('Successfully fetched power status!')
                print (f'(took {total_time}s)\n')
                return 0
        else:
            print('Unable to retrieve power status via IPMI.\n')
            return 1
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) fetching power status!\n')
        return 1
    except subprocess.SubprocessError:
        print ('Error calling pwr_status() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke ipmi-chassis!\n')
        return 1


def ipmi_channel(path_ipmi_config):
    print('-----------------------')
    print('Fetching IPMI channel:')
    start_time = time.clock()
    regex = re.compile('Section User')
    matches = 0
    channel = []
    try:
        # test channels 0 - 15
        for i in range(15):
            process = subprocess.Popen(
                [path_ipmi_config, '--checkout', '--lan-channel-number', str(i)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = process.communicate(timeout=15)
            if re.search(regex, output.decode('utf-8')):
                matches += 1
                channel.append(i)
        if matches > 0:
            end_time = time.clock()
            total_time = "{0:.4f}".format(end_time - start_time)
            print ('IPMI Channel(s):', channel)
            print (f'(took {total_time}s)\n')
            return 0
        else:
            print ('Unable to fetch IPMI channel!')
            return 1
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) fetching IPMI channel!\n')
        return 1
    except subprocess.SubprocessError:
        print ('Error calling ipmi_channel() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke ipmi-config!\n')
        return 1


def bmc_info(path_bmc_info):
    print('-----------------------')
    print('Fetching BMC information:')
    start_time = time.clock()
    try:
        fnull = open(os.devnull, 'w')
        subprocess.check_call(
            [path_bmc_info],
            stdout=fnull, stderr=subprocess.PIPE, timeout=15)
        end_time = time.clock()
        total_time = "{0:.4f}".format(end_time - start_time)
        print('Successfully fetched chassis status!')
        print (f'(took {total_time}s)\n')
        return 0
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) fetching BMC information!\n')
        return 1
    except subprocess.CalledProcessError:
        print ('Error calling bmc-info() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke bmc-info!\n')
        return 1


def ipmi_version(path_bmc_info):
    print('-----------------------')
    print('Testing IPMI version:')
    start_time = time.clock()
    try:
        process = subprocess.Popen(
            [path_bmc_info],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate(timeout=15)
        output = output.decode('utf-8')
        # Prefer .index() over .find() for exception handling
        res_index = output.index('IPMI Version')
        version = output[(res_index + 24):(res_index + 27)]
        print ('IPMI Version:', version)
        if float(version) < 2.0:
            print ('IPMI Version below 2.0!')
            return 1
        else:
            end_time = time.clock()
            total_time = "{0:.4f}".format(end_time - start_time)
            print (f'(took {total_time}s)\n')
            return 0
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) fetching IPMI version!\n')
        return 1
    except subprocess.SubprocessError:
        print ('Error calling ipmi_version() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke bmc-info!\n')
        return 1


def ipmi_locate(path_ipmi_locate):
    print('-----------------------')
    print('Testing ipmi-locate:')
    start_time = time.clock()
    try:
        fnull = open(os.devnull, 'w')
        subprocess.check_call(
            [path_ipmi_locate],
            stdout=fnull, stderr=subprocess.PIPE, timeout=15)
        end_time = time.clock()
        total_time = "{0:.4f}".format(end_time - start_time)
        print('Successfully called ipmi-locate!')
        print (f'(took {total_time}s)\n')
        return 0
    except subprocess.TimeoutExpired as e:
        print (f'Timeout ({e.timeout}s) testing impmi-locate!\n')
        return 1
    except subprocess.CalledProcessError:
        print ('Error calling impi_locate() subprocess!\n')
        return 1
    except EnvironmentError:
        print ('Unable to invoke ipmi-locate!\n')
        return 1


# call main()
if __name__ == '__main__':
    main()
