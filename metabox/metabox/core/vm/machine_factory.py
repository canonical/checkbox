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

from metabox.core.vm.docker_machine import ContainerDockerMachine
from metabox.core.machine import ContainerSnapMachine, ContainerPPAMachine, ContainerSourceMachine

def machine_selector(config, container):
    runtime = os.environ.get('METABOX_RUNTIME_ENV', 'lxd')
    if config.origin in ('snap', 'classic-snap'):
        assert runtime == 'lxd', f'Runtime {runtime} not supported for snap mode'
        return ContainerSnapMachine(config, container)
    elif config.origin == 'ppa':
        assert runtime == 'lxd', f'Runtime {runtime} not supported for PPA mode'
        return ContainerPPAMachine(config, container)
    elif config.origin == 'source':
        if runtime == 'docker':
            return ContainerDockerMachine(config, container)
        else:
            return ContainerSourceMachine(config, container)
