# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

from unittest import TestCase

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline


CL1 = """\
BOOT_IMAGE=(hd1,gpt1)/EFI/ubuntu/pc-kernel_x1/kernel.img root=LABEL=writable \
snap_core=core_1.snap snap_kernel=pc-kernel_1.snap ro net.ifnames=0 \
init=/lib/systemd/systemd console=tty1 panic=-1 pci=nomsi"""


class TestKernelCmdlineParser(TestCase):

    def test_parser_CL1(self):
        result = parse_kernel_cmdline(CL1)
        expected_flags = ['ro']
        self.assertListEqual(result.flags, expected_flags)
        expected_params = {
            'BOOT_IMAGE': '(hd1,gpt1)/EFI/ubuntu/pc-kernel_x1/kernel.img',
            'root': "writable",
            'LABEL': "writable",
            'snap_core': "core_1.snap",
            'snap_kernel': "pc-kernel_1.snap",
            'net.ifnames': "0",
            'init': "/lib/systemd/systemd",
            'console': "tty1",
            'panic': "-1",
            'pci': "nomsi"
        }
        self.assertDictEqual(result.params, expected_params)
