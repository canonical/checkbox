#!/usr/bin/env python3
# Copyright 2016 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

import checkbox_support.bt_helper as bt_helper


def main():
    mgr = bt_helper.BtManager()
    mgr.ensure_adapters_powered()
    print('Make sure that the keyboard is turned on and is in pairable state.')
    print('Then press ENTER')
    input()
    print('Scanning for devices...')
    mgr.scan()

    keyboards = sorted(mgr.get_bt_devices(
        category=bt_helper.BT_KEYBOARD, filters={'Paired': False}),
         key=lambda x: int(x.rssi or -255), reverse=True)
    if not keyboards:
        print("No keyboards detected")
        return
    print('Detected keyboards (sorted by RSSI; highest first).')
    # let's assing numbers to keyboards
    keyboards = dict(enumerate(keyboards, 1))
    for num, kb in keyboards.items():
        print('{}. {} (RSSI: {})'.format(num, kb, kb.rssi))
    chosen = False
    while not chosen:
        print('Which one would you like to connect to? (0 to exit) ',
              flush=True)
        num = input()
        if num == '0':
            return
        chosen = num.isnumeric() and int(num) in keyboards.keys()
    kb = keyboards[int(num)]
    print('{} chosen. Pairing...'.format(kb))
    kb.pair()
    print(('Try typing on a keyboard. '
           'Type "quit" and press ENTER to end the test.'))
    while input().lower() != 'quit':
        pass
    print('Unpairing the keyboard...')
    kb.unpair()


if __name__ == '__main__':
    main()
