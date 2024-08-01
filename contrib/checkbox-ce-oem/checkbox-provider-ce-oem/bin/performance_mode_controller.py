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

    # Get the full path of the specific python module which implements the
    # real logic to control the enable and disable performance mode.
    # In this way, we can leverage the perfromance python module which be
    # implemented at each project checkbox instead of duplicating same script
    # in ce-oem provider.
    # It's the empty value by defaul, you have to define it as Checkbox's
    # configuraion.
    PERFORMANCE_PYTHON_MODULE_PATH = os.environ.get(
        "PERFORMANCE_PYTHON_MODULE_PATH", ""
    )
    if not os.path.exists(PERFORMANCE_PYTHON_MODULE_PATH):
        raise FileNotFoundError(
            (
                "Fail to get the full path of performance python module. "
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


class ModuleLoader:
    """
    A class to load Python modules dynamically from a given file path.

    Attributes:
    -----------
    module_name : str
        The name to assign to the module once it's loaded.
    full_path : str
        The full file path to the module.
    module : Optional[object]
        The loaded module object, initialized to None.

    Methods:
    --------
    load_module() -> None:
        Loads the module from the specified file path.
    get_function(func_name: str) -> Callable:
        Retrieves a function from the loaded module.
    """

    def __init__(self, module_name: str, full_path: str):
        """
        Initializes the ModuleLoader with the given module name and path.

        Parameters:
        -----------
        module_name : str
            The name to assign to the module once it's loaded.
        full_path : str
            The full file path to the module.
        """
        self.module_name = module_name
        self.full_path = full_path
        self.module: Optional[object] = None

    def load_module(self) -> None:
        """
        Loads the module from the specified file path.

        Raises:
        -------
        FileNotFoundError:
            If the module file does not exist.
        """
        try:
            loader = SourceFileLoader(self.module_name, self.full_path)
            spec = importlib.util.spec_from_loader(self.module_name, loader)
            self.module = importlib.util.module_from_spec(spec)
            loader.exec_module(self.module)
        except FileNotFoundError:
            logging.error(
                "Module '{}' cannot be loaded since '{}' doesn't exist".format(
                    self.module_name, self.full_path
                )
            )
            raise

    def get_function(self, func_name: str) -> Callable:
        """
        Retrieves a function from the loaded module.

        Parameters:
        -----------
        func_name : str
            The name of the function to retrieve.

        Returns:
        --------
        Callable:
            The function object from the module.

        Raises:
        -------
        AttributeError:
            If the function is not found in the module.
        """
        if self.module is None:
            self.load_module()
        try:
            return getattr(self.module, func_name)
        except AttributeError:
            logging.error(
                "Function '{}' not found in module '{}'".format(
                    func_name, self.module_name
                )
            )
            raise


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
        return ModuleLoader(module_name, module_path).get_function(
            function_name
        )
    except Exception:
        raise SystemExit()
