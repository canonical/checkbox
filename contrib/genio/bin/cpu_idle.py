#!/usr/bin/env python3

import os
import argparse


GENERAL_PATH = 'cpu%d/cpuidle/state%d/%s'


def read_attr(attr):
    path = os.path.join('/sys/devices/system/cpu', attr)
    if not os.path.exists(path):
        return ''
    with open(path) as f:
        tmp = f.read().strip()
        return tmp


def read_attr_num(attr):
    tmp = read_attr(attr)
    if not tmp:
        return -1

    return int(tmp)


def read_idle_attr(cpu, state, attr):
    return read_attr(GENERAL_PATH % (cpu, state, attr))


def read_idle_attr_num(cpu, state, attr):
    return read_attr_num(GENERAL_PATH % (cpu, state, attr))


def error_handler(node_type, node_path, expect, reality):
    if node_type == 'name' or node_type == 'disable':
        print(
            (
                f"Failed: "
                f"the expected {node_type} value of node '{node_path}' "
                f"should be '{expect}' but got '{reality}'"
            )
        )
    if node_type == 'usage':
        print(
            (
                f"Failed: "
                f"the expected usage value of node '{node_path}' "
                f"should grater than 0"
            )
        )


def output_checker(cpu, state, name, disable, usage):
    '''
        @param:name, type: tuple. (reality value, expected value)
        @param:disable, type: tuple. (reality value, expected value)
        @param:usage
    '''
    fail = 0
    print(f'CPU node: cpu/{cpu}/cpuidle/state{state}')
    print(f'Got name: {name[0]}, disable: {disable[0]}, usage: {usage}')
    if name[0] != name[1]:
        node_path = GENERAL_PATH.format(cpu, state, 'name')
        error_handler('name', node_path, name[0], name[1])
        fail = 1
    if disable[0] != disable[1]:
        node_path = GENERAL_PATH.format(cpu, state, 'disable')
        error_handler('disable', node_path, disable[0], disable[1])
        fail = 1
    if usage <= 0:
        node_path = GENERAL_PATH.format(cpu, state, 'usage')
        error_handler('usage', node_path)
        fail = 1
    if fail:
        exit(1)


def test_wfi():
    cpu = 0
    state = 0
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'WFI'),
        disable=(disable, '0'),
        usage=usage
    )


def test_mcdi_cpu(soc):
    if soc != 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 0
    state = 1
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'mcdi-cpu'),
        disable=(disable, '0'),
        usage=usage
    )


def test_mcdi_cluster(soc):
    if soc != 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 0
    state = 2
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'mcdi-cluster'),
        disable=(disable, '0'),
        usage=usage
    )


def test_dpidle(soc):
    if soc != 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 0
    state = 3
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'dpidle'),
        disable=(disable, '0'),
        usage=usage
    )


def test_clusteroff_l(soc):
    if soc == 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 0
    state = 2
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'clusteroff-l' if soc == 'mt8390' else 'clusteroff_l'),
        disable=(disable, '0'),
        usage=usage
    )


def test_clusteroff_b(soc):
    if soc == 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 6 if soc == 'mt8390' else 4
    state = 2
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'clusteroff-b' if soc == 'mt8390' else 'clusteroff_b'),
        disable=(disable, '0'),
        usage=usage
    )


def test_cpuoff_l(soc):
    if soc == 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 0
    state = 1
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'cpuoff-l' if soc == 'mt8390' else 'cpuoff_l'),
        disable=(disable, '0'),
        usage=usage
    )


def test_cpuoff_b(soc):
    if soc == 'mt8365':
        print(f"Isn't supported for '{soc}'")
        return

    cpu = 6 if soc == 'mt8390' else 4
    state = 1
    name = read_idle_attr(cpu, state, 'name')
    disable = read_idle_attr(cpu, state, 'disable')
    usage = read_idle_attr_num(cpu, state, 'usage')
    output_checker(
        cpu,
        state,
        name=(name, 'cpuoff-b' if soc == 'mt8390' else 'cpuoff_b'),
        disable=(disable, '0'),
        usage=usage
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'soc',
        help='SoC type. e.g mt8395',
        choices=['mt8395', 'mt8390', 'mt8365']
    )
    parser.add_argument(
        '-c', '--case',
        help='The available cases of CPU Idle',
        choices=[
            'wfi', 'mcdi-cpu', 'mcdi-cluster', 'dpidle', 'clusteroff-l',
            'clusteroff-b', 'cpuoff-l', 'cpuoff-b'
        ],
        type=str,
        required=True
    )
    args = parser.parse_args()
    if args.case == 'wfi':
        test_wfi()
    if args.case == 'mcdi-cpu':
        test_mcdi_cpu(args.soc)
    if args.case == 'mcdi-cluster':
        test_mcdi_cluster(args.soc)
    if args.case == 'dpidle':
        test_dpidle(args.soc)
    if args.case == 'clusteroff-l':
        test_clusteroff_l(args.soc)
    if args.case == 'clusteroff-b':
        test_clusteroff_b(args.soc)
    if args.case == 'cpuoff-l':
        test_cpuoff_l(args.soc)
    if args.case == 'cpuoff-b':
        test_cpuoff_b(args.soc)


if __name__ == '__main__':
    main()
