# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hector Cao <hector.cao@canonical.com>
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

from abc import ABC, abstractmethod

class AbstractMachineProvider(ABC):

    @abstractmethod
    def __init__(self, session_config, effective_machine_config,
                 debug_machine_setup=False, dispose=False):
        pass

    @abstractmethod
    def setup(self):
        pass
    
    def cleanup(self, dispose=False):
        pass
