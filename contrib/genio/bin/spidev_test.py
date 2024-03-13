#!/usr/bin/env python3

import os
import argparse
import subprocess

PLAINBOX_PROVIDER_DATA = os.environ.get('PLAINBOX_PROVIDER_DATA')


def runcmd(command):
    ret = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        timeout=1
    )
    return ret


def check_spi_node(path):
    print("Checking whether SPI node {} exists".format(path))
    if os.path.exists(path):
        print("PASS: SPI node {} exist!\n".format(path))
    else:
        raise SystemExit("ERROR: SPI node {} does NOT exist!".format(path))


def test_spi_content_consistency(platform):
    spi_path = '/dev/spidev0.0'
    if platform == 'G1200-evk':
        spi_path = '/dev/spidev1.0'

    check_spi_node(spi_path)

    test_bin_path = f'{PLAINBOX_PROVIDER_DATA}/spi/test.bin'
    cmd = (
        f'genio-test-tool.spidev-test -D'
        f' {spi_path} -s 400000 -i {test_bin_path} -v'
    )
    print(f'Run command: {cmd}\n')
    spi_ret = runcmd([cmd])
    print(spi_ret.stdout)

    if spi_ret.stdout == "":
        raise SystemExit(
            'ERROR: no any output be reported')

    packets = spi_ret.stdout.split('\n')
    for rx, tx in zip(packets[-2:-1], packets[-3:-2]):
        tx_content = tx.split('|')[2]
        rx_content = rx.split('|')[2]
        if tx_content != rx_content:
            raise SystemExit(
                'ERROR: the content is not consistent between TX and RX')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'platform',
        help='Device platform. e.g G1200-evk',
        choices=['G1200-evk', 'G700', 'G350']
    )
    args = parser.parse_args()
    test_spi_content_consistency(args.platform)


if __name__ == "__main__":
    main()
