#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2022 Canonical Ltd.
# Written by:
#   Rod Smith <rod.smith@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from natsort import natsorted
import unittest


class TestSortingOfNetworkSpeeds(unittest.TestCase):

    def test_sortspeeds(self):
        # Input taken from cloaker's ens1f0, a Mellanox ConnectX-5 Ex
        input = ['1000baseKX/Full', '10000baseKR/Full', '40000baseKR4/Full',
                 '40000baseCR4/Full', '40000baseSR4/Full',
                 '40000baseLR4/Full', '25000baseCR/Full', '25000baseKR/Full',
                 '25000baseSR/Full', '50000baseCR2/Full', '50000baseKR2/Full',
                 '100000baseKR4/Full', '100000baseSR4/Full',
                 '100000baseCR4/Full', '100000baseLR4_ER4/Full']
        expected_output = ['1000baseKX/Full', '10000baseKR/Full',
                           '25000baseCR/Full', '25000baseKR/Full',
                           '25000baseSR/Full', '40000baseCR4/Full',
                           '40000baseKR4/Full', '40000baseLR4/Full',
                           '40000baseSR4/Full', '50000baseCR2/Full',
                           '50000baseKR2/Full', '100000baseCR4/Full',
                           '100000baseKR4/Full', '100000baseLR4_ER4/Full',
                           '100000baseSR4/Full']
        output = natsorted(input)
        self.assertEqual(expected_output, output)
