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

import os
from abc import ABC, abstractmethod

from loguru import logger

from metabox.core.vm.docker_provider import DockerMachineProvider
from metabox.core.lxd_provider import LxdMachineProvider

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

class MachineProviderFactory():
    
    @staticmethod
    def create(*args, **kwargs):
        if os.environ.get('METABOX_RUNTIME_ENV') == 'docker':
            logger.warning('Using docker runtime')
            return DockerMachineProvider(*args, **kwargs)
        else:
            logger.warning('Using LXD runtime')
            return LxdMachineProvider(*args, **kwargs)