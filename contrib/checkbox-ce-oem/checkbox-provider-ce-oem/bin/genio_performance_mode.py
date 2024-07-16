#!/usr/bin/env python3
# This script is used to all genio boards and should be run as a super user

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

import contextlib
import logging
import os
import re

logging.basicConfig(level=logging.INFO)

SYS_DEVICES_CPU = "/sys/devices/system/cpu"
PATH_CPU_GOVERNOR = SYS_DEVICES_CPU + "/cpufreq/policy{}/scaling_governor"
PATH_CPUIDLE_STATE_DISABLE = SYS_DEVICES_CPU + "/cpu{}/cpuidle/state{}/disable"
PATH_GPU_GOVERNOR = "/sys/devices/platform/soc/{}/devfreq/{}/governor"
SYS_CLASS_THERMAL_ZONE = "/sys/class/thermal/thermal_zone{}"
PATH_OF_THERMAL_MODE = SYS_CLASS_THERMAL_ZONE + "/mode"
PATH_OF_THERMAL_TRIP_POINT = SYS_CLASS_THERMAL_ZONE + "/trip_point_{}_temp"
BACKUP_CPU_GOVERNOR_STR_TEMPLEATE = "/tmp/p_{}_sg"
BACKUP_GPU_GOVERNOR_STR_TEMPLEATE = "/tmp/soc_{}_g"
BACKUP_THERMAL_TRIP_POINT_STR_TEMPLEATE = "/tmp/thermal_{}_trip_{}_temp"
BACKUP_THERMAL_MODE_STR_TEMPLEATE = "/tmp/thermal_{}_mode"
BACKUP_CPUIDEL_STATE_DISABLE_STR_TEMPLEATE = "/tmp/c_{}_s_{}_disable"


class PerformanceController():
    '''
    PerformanceController provides some methods that handle the get, set and
    backup actions.
    '''
    def _get_node_value(self, node_path):
        with open(node_path, 'r') as f:
            value = f.read().strip()
            return value

    def _set_node_value(self, node_path, value):
        with open(node_path, 'w') as out:
            out.write(str(value))

    def _get_cpu_governor(self, policy):
        node_path = PATH_CPU_GOVERNOR.format(policy)
        governor = self._get_node_value(node_path=node_path)
        return governor

    def _set_cpu_governor(self, governor_mode, policy):
        node_path = PATH_CPU_GOVERNOR.format(policy)
        self._set_node_value(node_path=node_path, value=governor_mode)

    def _get_gpu_governor(self, soc):
        node_path = PATH_GPU_GOVERNOR.format(soc, soc)
        governor = self._get_node_value(node_path=node_path)
        return governor

    def _set_gpu_governor(self, governor_mode, soc):
        node_path = PATH_GPU_GOVERNOR.format(soc, soc)
        self._set_node_value(node_path=node_path, value=governor_mode)

    def _get_thermal_trip_point_temp(self, thermal_zone, trip_point_count):
        node_path = PATH_OF_THERMAL_TRIP_POINT.format(
            thermal_zone, trip_point_count)
        temp_value = self._get_node_value(node_path=node_path)
        return temp_value

    def _set_thermal_trip_point_temp(
        self, thermal_zone, trip_point_count, temp_value
    ):
        node_path = PATH_OF_THERMAL_TRIP_POINT.format(
            thermal_zone, trip_point_count)
        self._set_node_value(node_path=node_path, value=temp_value)

    def _set_apusys(self, value):
        node_path = "/sys/kernel/debug/apusys/power"
        self._set_node_value(node_path=node_path, value=value)

    def _toggle_cpuidle_state_disable(self, cpu_count, state_count, value):
        '''
        Toggle the 'disable' attribute for CPU idle states.

        Args:
            cpu_count (int): The count of CPUs.
            state_count (int): The count of CPU idle stat.
            value (int):
                The value to set for the 'disable' attribute (0 or 1).

        Raises:
            ValueError: If the provided value is not 0 or 1.
        '''
        if value not in [0, 1]:
            raise ValueError("Value must be 0 or 1")
        self._set_node_value(
            PATH_CPUIDLE_STATE_DISABLE.format(cpu_count, state_count), value)

    def _toggle_thermal_mode(self, thermal_zone, value):
        if value not in ["disabled", "enabled"]:
            raise ValueError("Thermal mode must be enabled or disabled")
        self._set_node_value(
            PATH_OF_THERMAL_MODE.format(thermal_zone), value)


class PerformanceModeManager(PerformanceController):
    '''
    PerformanceModeManager class for managing system performance modes.

    This class extends the PerformanceController class and provides methods
    to set and restore performance modes for CPU, GPU, APU, and thermal
    configurations.

    Args:
        affected_policies (list): List of affected CPU policies.
        affected_thermal_zone (int): Thermal zone to be affected.
        affected_thermal_trip_points (list):
            List of thermal trip points to be affected.
        affected_trip_point_temp (int):
            Temperature value for affected thermal trip points.
        change_thermal_mode (bool):
            Flag to indicate if thermal mode should be changed.
        gpu_soc_name (str): Name of the GPU SoC to be affected.
        enable_apu (bool): Flag to indicate if APU should be enabled.

    Methods:
        set_performance_mode():
            Configures CPU, GPU, APU and thermal settings for performance mode.

        restore_default_mode():
            Restores default CPU, GPU and thermal settings.

    Note:
        This class assumes the existence of methods such as
        _backup_cpu_governor, _set_cpu_governor, _toggle_cpuidle_state_disable,
        _backup_gpu_governor, _set_gpu_governor, _set_apusys,
        _toggle_thermal_mode, _backup_thermal_trip_point_temp,
        _set_thermal_trip_point_temp, _restore_cpu_governor,
        _restore_gpu_governor, and _restore_thermal_trip_point_temp
        in the parent class (PerformanceController).
    '''
    def __init__(
        self,
        affected_policies: list,
        affected_thermal_zone: int,
        affected_thermal_trip_points: list,
        affected_trip_point_temp: int,
        change_thermal_mode: bool,
        gpu_soc_name: str,
        enable_apu: bool
    ):
        self._affected_policies = affected_policies
        self._affected_thermal_zone = affected_thermal_zone
        self._affected_thermal_trip_points = affected_thermal_trip_points
        self._affected_trip_point_temp = affected_trip_point_temp
        self._change_thermal_mode = change_thermal_mode
        self._gpu_soc_name = gpu_soc_name
        self._enable_apu = enable_apu
        self._affected_cpuidle_count_state = self._extract_cpu_state_numbers()

    def set_performance_mode(self):
        '''
        Set performance mode by configuring CPU, GPU, APU, and thermal
        settings.

        This method iterates over affected CPU policies, sets CPU governors to
        "performance", toggles CPU idle state, sets GPU governor to
        "performance", sets APU configuration, and adjusts thermal settings
        based on provided parameters.
        '''
        # Configure CPU
        for policy in self._affected_policies:
            self._backup_cpu_governor(policy)
            self._set_cpu_governor(
                governor_mode="performance", policy=policy)
        for item in self._affected_cpuidle_count_state:
            self._backup_cpuidle_state_disable(item[0], item[1])
            self._toggle_cpuidle_state_disable(item[0], item[1], 1)
        # Configure GPU
        if self._gpu_soc_name:
            self._backup_gpu_governor(soc=self._gpu_soc_name)
            self._set_gpu_governor(
                governor_mode="performance", soc=self._gpu_soc_name)
        # Configure APU
        if self._enable_apu:
            self._set_apusys(value="dvfs_debug 0")
        # Configure Thermal
        if self._change_thermal_mode:
            self._backup_thermal_mode()
            self._toggle_thermal_mode(self._affected_thermal_zone, "disabled")
        if self._affected_thermal_trip_points and \
                self._affected_trip_point_temp:
            for trip_point in self._affected_thermal_trip_points:
                self._backup_thermal_trip_point_temp(
                    thermal_zone=self._affected_thermal_zone,
                    trip_point_count=trip_point
                )
                self._set_thermal_trip_point_temp(
                    thermal_zone=self._affected_thermal_zone,
                    trip_point_count=trip_point,
                    temp_value=self._affected_trip_point_temp
                )

    def restore_default_mode(self):
        # Configure CPU
        for policy in self._affected_policies:
            self._restore_cpu_governor(policy)
        for item in self._affected_cpuidle_count_state:
            self._restore_cpuidle_state(item[0], item[1])
        # Configure GPU
        if self._gpu_soc_name:
            self._restore_gpu_governor(soc=self._gpu_soc_name)
        # Configure Thermal
        if self._change_thermal_mode:
            self._restore_thermal_mode()
        if self._affected_thermal_trip_points and \
                self._affected_trip_point_temp:
            for trip_point in self._affected_thermal_trip_points:
                self._restore_thermal_trip_point_temp(
                    thermal_zone=self._affected_thermal_zone,
                    trip_point_count=trip_point
                )

    def _backup_cpu_governor(self, policy):
        governor = self._get_cpu_governor(policy)
        self._set_node_value(
            node_path=BACKUP_CPU_GOVERNOR_STR_TEMPLEATE.format(policy),
            value=governor
        )

    def _restore_cpu_governor(self, policy):
        origianl_value = self._get_node_value(
            BACKUP_CPU_GOVERNOR_STR_TEMPLEATE.format(policy))
        self._set_cpu_governor(governor_mode=origianl_value, policy=policy)

    def _backup_cpuidle_state_disable(self, cpu_count, state_count):
        value = self._get_node_value(
            PATH_CPUIDLE_STATE_DISABLE.format(cpu_count, state_count))
        self._set_node_value(
            BACKUP_CPUIDEL_STATE_DISABLE_STR_TEMPLEATE.format(
                cpu_count, state_count),
            value
        )

    def _restore_cpuidle_state(self, cpu_count, state_count):
        origianl_value = self._get_node_value(
            BACKUP_CPUIDEL_STATE_DISABLE_STR_TEMPLEATE.format(
                cpu_count, state_count))
        self._toggle_cpuidle_state_disable(
            cpu_count, state_count, int(origianl_value))

    def _extract_cpu_state_numbers(self):
        '''
        Extracts CPU state numbers from files in the specified directory.

        Returns:
        - List of tuples:
            Each tuple contains two integers representing CPU numbers (X) and
            state numbers (Y).
        '''
        pattern = re.compile(r'/cpu(\d+)/cpuidle/state(\d+)/disable')
        results = []

        # Walk through the directory and its subdirectories
        for root, _, files in os.walk(SYS_DEVICES_CPU):
            for file in files:
                # Construct the full path for each file
                full_path = os.path.join(root, file)

                # Use the regular expression pattern to directly extract
                # numbers
                match = pattern.search(full_path)
                if match:
                    results.append((int(match.group(1)), int(match.group(2))))

        return results

    def _backup_gpu_governor(self, soc):
        governor = self._get_gpu_governor(soc)
        self._set_node_value(
            node_path=BACKUP_GPU_GOVERNOR_STR_TEMPLEATE.format(soc),
            value=governor
        )

    def _restore_gpu_governor(self, soc):
        origianl_value = self._get_node_value(
            BACKUP_GPU_GOVERNOR_STR_TEMPLEATE.format(soc))
        self._set_gpu_governor(governor_mode=origianl_value, soc=soc)

    def _backup_thermal_mode(self):
        value = self._get_node_value(node_path=PATH_OF_THERMAL_MODE.format(
            self._affected_thermal_zone))
        self._set_node_value(
            node_path=BACKUP_THERMAL_MODE_STR_TEMPLEATE.format(
                self._affected_thermal_zone),
            value=value
        )

    def _restore_thermal_mode(self):
        origianl_value = self._get_node_value(
            BACKUP_THERMAL_MODE_STR_TEMPLEATE.format(
                self._affected_thermal_zone))
        self._toggle_thermal_mode(self._affected_thermal_zone, origianl_value)

    def _backup_thermal_trip_point_temp(self, thermal_zone, trip_point_count):
        temp_value = self._get_thermal_trip_point_temp(
            thermal_zone=thermal_zone, trip_point_count=trip_point_count)
        self._set_node_value(
            node_path=BACKUP_THERMAL_TRIP_POINT_STR_TEMPLEATE.format(
                thermal_zone, trip_point_count),
            value=temp_value
        )

    def _restore_thermal_trip_point_temp(self, thermal_zone, trip_point_count):
        origianl_temp = self._get_node_value(
            BACKUP_THERMAL_TRIP_POINT_STR_TEMPLEATE.format(
                thermal_zone, trip_point_count))
        self._set_thermal_trip_point_temp(
            thermal_zone=thermal_zone,
            trip_point_count=trip_point_count,
            temp_value=origianl_temp)


def get_testing_parameters(platform):
    """
    Get testing parameters based on the specified platform.

    Args:
        platform (str): The platform identifier.

    Returns:
        dict: A dictionary containing testing parameters for the given
            platform.
              The keys and values may include:
              - 'affected_policies' (list): List of affected CPU policies.
              - 'affected_cpuidle_count_state' (list):
                    List containing CPU idle count and state.
              - 'affected_thermal_zone' (int): Thermal zone to be affected.
              - 'affected_thermal_trip_points' (list):
                    List of affected thermal trip points.
              - 'affected_trip_point_temp' (int):
                    Temperature value for affected thermal trip points.
              - 'change_thermal_mode' (bool):
                    Flag to indicate if thermal mode should be changed.
              - 'gpu_soc_name' (str): Name of the GPU SoC to be affected.
              - 'enable_apu' (bool): Flag to indicate if APU should be enabled.
    """
    testing_params = {}
    if platform == "genio-1200":
        testing_params = {
            "affected_policies": [0, 4],
            "affected_thermal_zone": 0,
            "affected_thermal_trip_points": [],
            "affected_trip_point_temp": 0,
            "change_thermal_mode": True,
            "gpu_soc_name": "13000000.mali",
            "enable_apu": True,
        }
    elif platform == "genio-700":
        testing_params = {
            "affected_policies": [0, 6],
            "affected_thermal_zone": 0,
            "affected_thermal_trip_points": [0, 1, 2],
            "affected_trip_point_temp": 1115000,
            "change_thermal_mode": True,
            "gpu_soc_name": "13000000.mali",
            "enable_apu": True,
        }
    elif platform == "genio-510":
        testing_params = {
            "affected_policies": [0, 4],
            "affected_thermal_zone": 0,
            "affected_thermal_trip_points": [0, 1, 2],
            "affected_trip_point_temp": 1115000,
            "change_thermal_mode": True,
            "gpu_soc_name": "13000000.mali",
            "enable_apu": True,
        }
    elif platform == "genio-350":
        testing_params = {
            "affected_policies": [0],
            "affected_thermal_zone": 0,
            "affected_thermal_trip_points": [],
            "affected_trip_point_temp": 0,
            "change_thermal_mode": True,
            "gpu_soc_name": "13040000.mali",
            "enable_apu": False,
        }

    return testing_params


@contextlib.contextmanager
def performance_mode(target: str):
    # Run Performance Mode
    try:
        logging.info("======== Enable Performance Mode ========")
        testing_params = get_testing_parameters(target)
        PerformanceModeManager(**testing_params).set_performance_mode()
        yield
    finally:
        logging.info("======== Disable Performance Mode ========")
        PerformanceModeManager(**testing_params).restore_default_mode()
