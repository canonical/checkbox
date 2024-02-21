# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
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

import unittest

from unittest.mock import MagicMock, patch

from checkbox_support.interactive_cmd import InteractiveCommand

class InteractiveCommandTests(unittest.TestCase):

    @patch('sys.stdin')
    def test_write_line_nominal(self, mock_stdin):
        mock_self = MagicMock()
        mock_stdin.encoding = 'utf-8'
        InteractiveCommand.writeline(mock_self, 'Hello, world!')
        mock_self._proc.stdin.write.assert_called_with(b'Hello, world!\n')

    @patch('sys.stdin')
    def test_write_line_broken_pipe(self, mock_stdin):
        mock_self = MagicMock()
        mock_self._proc.stdin.write.side_effect = BrokenPipeError
        mock_stdin.encoding = 'utf-8'
        mock_self.read_all.return_value = 'my pipe is gonna break'
        with self.assertRaises(BrokenPipeError):
            InteractiveCommand.writeline(mock_self, 'Hello, world!')
        
        mock_self._logger.warning.assert_called_with(
            "The output before the pipe broke: %s",
            "my pipe is gonna break")
        mock_self._proc.stdin.write.assert_called_with(b'Hello, world!\n')    