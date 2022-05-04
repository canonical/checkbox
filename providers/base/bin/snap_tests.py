#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import os
import sys

from checkbox_support.snap_utils.snapd import Snapd

# Requirements for the test snap:
#  - the snap must be strictly confined (no classic or devmode flags)
#  - there must be different revisions on the stable & edge channels
try:
    TEST_SNAP = os.environ['TEST_SNAP']
except KeyError:
    runtime = os.getenv('CHECKBOX_RUNTIME', '/snap/checkbox/current')
    if 'checkbox18' in runtime:
        TEST_SNAP = 'test-snapd-tools-core18'
    elif 'checkbox20' in runtime:
        TEST_SNAP = 'test-snapd-tools-core20'
    elif 'checkbox22' in runtime:
        TEST_SNAP = 'test-snapd-tools-core22'
    else:
        TEST_SNAP = 'test-snapd-tools'
SNAPD_TASK_TIMEOUT = int(os.getenv('SNAPD_TASK_TIMEOUT', 30))
SNAPD_POLL_INTERVAL = int(os.getenv('SNAPD_POLL_INTERVAL', 1))


class SnapList():

    """snap list sub-command."""

    def invoked(self):
        """snap list should show the core package is installed."""
        data = Snapd().list()
        for snap in data:
            if snap['name'] in ('core', 'core16', 'core18', 'core20',
                                'core22'):
                print("Found a core snap")
                print(snap['name'], snap['version'], snap['revision'])
                return 0
        return 1


class SnapSearch():

    """snap search sub-command."""

    def invoked(self):
        """snap search for TEST_SNAP."""
        data = Snapd().find(TEST_SNAP,)
        for snap in data:
            print('ID:', snap['id'])
            print('Name:', snap['name'])
            print('Developer:', snap['developer'])
            return 0
        return 1


class SnapInstall():

    """snap install sub-command."""

    def invoked(self):
        """Test install of test-snapd-tools snap."""
        parser = argparse.ArgumentParser()
        parser.add_argument('channel', help='channel to install from')
        args = parser.parse_args(sys.argv[2:])
        print('Install {}...'.format(TEST_SNAP))
        s = Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL, verbose=True)
        if s.list(TEST_SNAP):
            print('{} already installed. Removing'.format(TEST_SNAP))
            s.remove(TEST_SNAP)
        s.install(TEST_SNAP, args.channel)
        print('Confirm in snap list...')
        data = s.list()
        for snap in data:
            if snap['name'] == TEST_SNAP:
                return 0
        print(' not in snap list')
        return 1


class SnapRefresh():

    """snap refresh sub-command."""

    def invoked(self):
        """Test refresh of test-snapd-tools snap."""
        s = Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL)
        if s.list(TEST_SNAP):
            print('Remove previously installed revision')
            s.remove(TEST_SNAP)
        print('Install starting revision...')
        s.install(TEST_SNAP, 'stable')
        start_rev = s.list(TEST_SNAP)['revision']
        print('  revision:', start_rev)
        print('Refresh to edge...')
        s.refresh(TEST_SNAP, 'edge')
        print('Get new revision...')
        new_rev = s.list(TEST_SNAP)['revision']
        print('  revision:', new_rev)
        if new_rev == start_rev:
            return 1
        return 0


class SnapRevert():

    """snap revert sub-command."""

    def invoked(self):
        """Test revert of test-snapd-tools snap."""
        s = Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL)
        if s.list(TEST_SNAP):
            s.remove(TEST_SNAP)
        print('Install stable revision')
        s.install(TEST_SNAP)
        print('Refresh to edge')
        s.refresh(TEST_SNAP, 'edge')
        print('Get stable channel revision from store...')
        r = s.info(TEST_SNAP)
        stable_rev = r['channels']['latest/stable']['revision']
        r = s.list(TEST_SNAP)
        installed_rev = r['revision']  # should be edge revision
        print('Reverting snap {}...'.format(TEST_SNAP))
        s.revert(TEST_SNAP)
        print('Get new installed revision...')
        r = s.list(TEST_SNAP)
        rev = r['revision']
        if rev != stable_rev:
            print("Not stable revision number")
            return 1
        if rev == installed_rev:
            print("Identical revision number")
            return 1
        return 0


class SnapReupdate():

    """snap reupdate sub-command."""

    def invoked(self):
        """Test re-update of test-snapd-tools snap."""
        s = Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL)
        print('Get edge channel revision from store...')
        if s.list(TEST_SNAP):
            s.remove(TEST_SNAP)
        s.install(TEST_SNAP)
        s.refresh(TEST_SNAP, 'edge')
        s.revert(TEST_SNAP)
        r = s.info(TEST_SNAP)
        edge_rev = r['channels']['latest/edge']['revision']
        print('Remove edge revision...')
        s.remove(TEST_SNAP, edge_rev)
        print('Refresh to edge channel...')
        s.refresh(TEST_SNAP, 'edge')
        print('Get new installed revision...')
        r = s.list(TEST_SNAP)
        rev = r['revision']
        if rev != edge_rev:
            print("Not edge revision number")
            return 1


class SnapRemove():

    """snap remove sub-command."""

    def invoked(self):
        """Test remove of test-snapd-tools snap."""
        print('Remove {}...'.format(TEST_SNAP))
        s = Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL)
        if not s.list(TEST_SNAP):
            print('{} not found. Installing'.format(TEST_SNAP))
            s.install(TEST_SNAP)
        s.remove(TEST_SNAP)
        print('Check not in snap list')
        data = s.list()
        for snap in data:
            if snap['name'] == TEST_SNAP:
                print(' found in snap list')
                return 1
        return 0


class Snap():

    """Fake snap like command."""

    def main(self):
        sub_commands = {
            'list': SnapList,
            'search': SnapSearch,
            'install': SnapInstall,
            'refresh': SnapRefresh,
            'revert': SnapRevert,
            'reupdate': SnapReupdate,
            'remove': SnapRemove
        }
        parser = argparse.ArgumentParser()
        parser.add_argument('subcommand', type=str, choices=sub_commands)
        args = parser.parse_args(sys.argv[1:2])
        return sub_commands[args.subcommand]().invoked()


if __name__ == '__main__':
    sys.exit(Snap().main())
