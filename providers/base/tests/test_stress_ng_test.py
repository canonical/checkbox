#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# Written by:
#   Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>
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

import unittest
from subprocess import CalledProcessError, TimeoutExpired
from unittest.mock import MagicMock, mock_open, patch

from stress_ng_test import main, num_numa_nodes, swap_space_ok


class TestMemoryFunctions(unittest.TestCase):
    @patch("stress_ng_test.run")
    def test_num_numa_nodes_success(self, run_mock):
        run_mock.return_value = MagicMock()
        run_mock.return_value.stdout = b"available: 2 nodes (0-1)"
        self.assertEqual(num_numa_nodes(), 2)

    @patch("stress_ng_test.run", side_effect=OSError)
    def test_num_numa_nodes_failure(self, run_mock):
        self.assertEqual(num_numa_nodes(), 1)

    @patch("psutil.swap_memory", return_value=MagicMock(total=1))
    def test_swap_space_ok_success(self, psutil_swap_memory_mock):
        self.assertTrue(swap_space_ok(0))

    @patch("stress_ng_test.run")
    @patch("os.chmod")
    @patch("stress_ng_test.open", new_callable=mock_open)
    @patch("stress_ng_test.range", return_value=[0])
    @patch(
        "psutil.swap_memory",
        side_effect=[MagicMock(total=0), MagicMock(total=1073741824)],
    )
    def test_swap_space_ok_create_swap(
        self,
        psutil_swap_memory_mock,
        open_mock,
        range_mock,
        os_chmod_mock,
        run_mock,
    ):
        self.assertTrue(swap_space_ok(1))

    @patch("stress_ng_test.run")
    @patch("os.chmod")
    @patch("stress_ng_test.open", side_effect=OSError)
    @patch("psutil.swap_memory", return_value=MagicMock(total=0))
    def test_swap_space_ok_remove_swap(
        self, psutil_swap_memory_mock, open_mock, os_chmod_mock, run_mock
    ):
        self.assertFalse(swap_space_ok(1))


@patch("os.geteuid", return_value=0)
@patch("shutil.which", return_value="/usr/bin/stress-ng")
class TestMainFunction(unittest.TestCase):
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_no_stress_ng(self, shutil_which_mock, os_geteuid_mock):
        shutil_which_mock.return_value = None
        self.assertEqual(main(), 1)

    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_not_root(self, shutil_which_mock, os_geteuid_mock):
        os_geteuid_mock.return_value = 1000
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=FileNotFoundError)
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_ng_not_found(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=TimeoutExpired(b"", 1))
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_timeout(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=KeyboardInterrupt)
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_keyboard_interrupt(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch(
        "stress_ng_test.check_output",
        side_effect=CalledProcessError(1, b"", b""),
    )
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_ng_error(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output")
    @patch("sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_cpu_success(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 0)

    @patch("os.remove")
    @patch("stress_ng_test.check_output")
    @patch("stress_ng_test.num_numa_nodes", return_value=1)
    @patch("stress_ng_test.swap_space_ok", return_value=True)
    @patch("sys.argv", ["stress_ng_test.py", "memory"])
    def test_main_stress_memory_success(
        self,
        shutil_which_mock,
        os_geteuid_mock,
        swap_space_ok_mock,
        num_numa_nodes_mock,
        check_output_mock,
        remove_mock,
    ):
        self.assertEqual(main(), 0)

    @patch("os.remove")
    @patch("stress_ng_test.check_output")
    @patch("stress_ng_test.num_numa_nodes", return_value=2)
    @patch("stress_ng_test.swap_space_ok", return_value=True)
    @patch("sys.argv", ["stress_ng_test.py", "memory"])
    def test_main_stress_memory_more_numa_nodes(
        self,
        shutil_which_mock,
        os_geteuid_mock,
        swap_space_ok_mock,
        num_numa_nodes_mock,
        check_output_mock,
        remove_mock,
    ):
        self.assertEqual(main(), 0)

    @patch("os.remove")
    @patch("stress_ng_test.Popen")
    @patch(
        "stress_ng_test.my_swap",
        return_value="/swap-df8a2b5f-d624-4e06-81bd-ec5e31aa213f",
    )
    @patch("stress_ng_test.check_output")
    @patch("stress_ng_test.num_numa_nodes", return_value=1)
    @patch("stress_ng_test.swap_space_ok", return_value=True)
    @patch("sys.argv", ["stress_ng_test.py", "memory"])
    def test_main_stress_memory_delete_swap(
        self,
        shutil_which_mock,
        os_geteuid_mock,
        swap_space_ok_mock,
        num_numa_nodes_mock,
        check_output_mock,
        my_swap_mock,
        popen_mock,
        os_remove_mock,
    ):
        self.assertEqual(main(), 0)

    @patch("stress_ng_test.swap_space_ok", return_value=False)
    @patch("sys.argv", ["stress_ng_test.py", "memory"])
    def test_main_stress_memory_not_enough_swap(
        self, shutil_which_mock, os_geteuid_mock, swap_space_ok_mock
    ):
        self.assertEqual(main(), 1)

    @patch("shutil.rmtree")
    @patch("stress_ng_test.check_output")
    @patch(
        "stress_ng_test.Disk",
        return_value=MagicMock(
            is_block_device=MagicMock(return_value=True),
            mount_filesystem=MagicMock(return_value=True),
        ),
    )
    @patch("sys.argv", ["stress_ng_test.py", "disk", "--device", "/dev/sda"])
    def test_main_stress_disk_success(
        self,
        shutil_which_mock,
        os_geteuid_mock,
        disk_mock,
        check_output_mock,
        rmtree_mock,
    ):
        self.assertEqual(main(), 0)

    @patch("shutil.rmtree")
    @patch("stress_ng_test.check_output")
    @patch(
        "stress_ng_test.Disk",
        return_value=MagicMock(
            is_block_device=MagicMock(return_value=True),
            mount_filesystem=MagicMock(return_value=True),
        ),
    )
    @patch("sys.argv", ["stress_ng_test.py", "disk", "--device", "sda"])
    def test_main_stress_disk_partial_name_success(
        self,
        shutil_which_mock,
        os_geteuid_mock,
        disk_mock,
        check_output_mock,
        rmtree_mock,
    ):
        self.assertEqual(main(), 0)

    @patch(
        "stress_ng_test.Disk",
        return_value=MagicMock(
            is_block_device=MagicMock(return_value=True),
            mount_filesystem=MagicMock(return_value=True),
        ),
    )
    @patch(
        "sys.argv",
        ["stress_ng_test.py", "disk", "--device", "/dev/sda", "--simulate"],
    )
    def test_main_stress_disk_simulate_success(
        self, shutil_which_mock, os_geteuid_mock, disk_mock
    ):
        self.assertEqual(main(), 0)

    @patch(
        "stress_ng_test.Disk",
        return_value=MagicMock(is_block_device=MagicMock(return_value=False)),
    )
    @patch("sys.argv", ["stress_ng_test.py", "disk", "--device", "/dev/sda"])
    def test_main_stress_disk_not_a_block_device(
        self, shutil_which_mock, os_geteuid_mock, disk_mock
    ):
        self.assertEqual(main(), 1)

    @patch(
        "stress_ng_test.Disk",
        return_value=MagicMock(
            is_block_device=MagicMock(return_value=True),
            mount_filesystem=MagicMock(return_value=False),
        ),
    )
    @patch("sys.argv", ["stress_ng_test.py", "disk", "--device", "/dev/sda"])
    def test_main_stress_disk_fail_mount(
        self, shutil_which_mock, os_geteuid_mock, disk_mock
    ):
        self.assertEqual(main(), 1)
