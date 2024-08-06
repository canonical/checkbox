#!/usr/bin/env python3
# Since there are lots of devices from different projects need to run case
# with Performance mode, therefore, this script aims to be an unified entry
# and can be called by other scripts. As for the detail of each device, we
# implement it in each different specific script.

# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

import importlib.util
import logging
import os
from importlib.machinery import SourceFileLoader
from typing import Callable, Optional


logging.basicConfig(level=logging.INFO)


def get_performance_ctx_function() -> Optional[Callable]:
    """
    Get the specific context manager function of controlling performance mode.
    The function helps you load a module which can not in the PYTHONPATH.
    Therefore, developers can implement the python script of controlling
    performance mode in each Checkbox Project and be used by ce-oem's script.

    Environment Variables:
    -----------
    PERFORMANCE_PYTHON_MODULE_PATH
        The full path of a python module that you are interested in even it's
        not in PYTHONPATH
    PERFORMANCE_FUNCTION_NAME
        The name of ctx function to control the performance in a module.

    Returns:
    --------
    Optional[Callable]:
        The function object if found

    Raises:
    -------
    SystemExit:
        If the module or function cannot be loaded, the program exits.
    """

    # Get the full path of the specific python module which implements the
    # real logic to control the enable and disable performance mode.
    # In this way, we can leverage the performance python module which be
    # implemented at each project checkbox instead of duplicating same script
    # in ce-oem provider.
    # It's the empty value by defaul, you have to define it as Checkbox's
    # configuraion.
    PERFORMANCE_PYTHON_MODULE_PATH = os.environ.get(
        "PERFORMANCE_PYTHON_MODULE_PATH", ""
    )
    if PERFORMANCE_PYTHON_MODULE_PATH == "":
        raise FileNotFoundError(
            (
                "Fail to get a performance python module"
                "Please define the path in Checkbox configuration. "
                "e.g. PERFORMANCE_PYTHON_MODULE_PATH=/path/of/the/module.py"
            )
        )

    # Get the name of context manager function which controls the performance
    # mode. Default name is performance_mode. You can assign the specific name
    # via environment variable
    PERFORMANCE_FUNCTION_NAME = os.environ.get(
        "PERFORMANCE_FUNCTION_NAME", "performance_mode"
    )

    return get_function_from_a_module(
        module_name=os.path.basename(PERFORMANCE_PYTHON_MODULE_PATH),
        module_path=PERFORMANCE_PYTHON_MODULE_PATH,
        function_name=PERFORMANCE_FUNCTION_NAME,
    )


def get_function_from_a_module(
    module_name: str,
    module_path: str,
    function_name: str,
) -> Optional[Callable]:
    """
    Loads a module and retrieves a specified function.

    Parameters:
    -----------
    module_name : str
        The name of the module to load.
    module_path : str
        The full file path to the module.
    function_name : str, optional
        The name of the function to retrieve from the module
        (default is "performance_mode").

    Returns:
    --------
    Optional[Callable]:
        The function object if found

    Raises:
    -------
    SystemExit:
        If the module or function cannot be loaded, the program exits.
    """
    try:
        logging.info(
            (
                "Trying to load the '{}' module from '{}' to get '{}'"
                " function"
            ).format(module_name, module_path, function_name)
        )
        loader = SourceFileLoader(module_name, module_path)
        spec = importlib.util.spec_from_loader(module_name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return getattr(module, function_name)
    except FileNotFoundError:
        logging.error(
            "Module '%s' cannot be loaded since '%s' doesn't exist",
            module_name,
            module_path,
        )
        raise
    except AttributeError:
        logging.error(
            "Function '%s' not found in module '%s'",
            function_name,
            module_name,
        )
        raise
