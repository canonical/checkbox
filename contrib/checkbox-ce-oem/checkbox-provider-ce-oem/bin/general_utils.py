import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json_file(
    json_file_path: str,
    enable_logger: bool = False,
) -> Dict[str, Any]:
    """Load a JSON file with executable-path validation semantics."""

    if not json_file_path or not isinstance(json_file_path, str):
        if enable_logger:
            logging.warning("Empty JSON file path provided, returning empty dictionary")
        return {}

    if not Path(json_file_path).is_absolute():
        plainbox_provider_data = os.getenv("PLAINBOX_PROVIDER_DATA", "")
        if not plainbox_provider_data:
            logging.error(
                "Relative executable JSON path requires "
                "PLAINBOX_PROVIDER_DATA: %s",
                json_file_path,
            )
        resolved_path = os.path.join(plainbox_provider_data, json_file_path)
    else:
        resolved_path = json_file_path

    try:
        if enable_logger:
            logging.info("Attempting to load JSON file: %s", resolved_path)
        with open(resolved_path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except FileNotFoundError:
        if enable_logger:
            logging.warning("JSON file not found: %s", resolved_path)
        return {}
    except (PermissionError, json.JSONDecodeError, OSError):
        if enable_logger:
            logging.warning("Failed to load JSON file: %s", resolved_path)
        return {}
        

def find_full_path_of_binary(command: str, enable_logger: bool = False,) -> str | None:
    """Find the full path of a command using the predefined priority order.

    Args:
        command: The command name to search for.

    Returns:
        The absolute path of the command if found, otherwise None.
    """
    search_paths = (
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/sbin"),
        Path("/sbin"),
        Path("/usr/local/bin"),
        Path("/usr/local/sbin"),
    )

    if Path(command).is_absolute() and Path(command).is_file():
        if enable_logger:
            logging.info("Command '%s' is an absolute path and exists", command)
        return command

    for directory in search_paths:
        command_path = directory / command

        if command_path.is_file() and command_path.stat().st_mode & 0o111:
            if enable_logger:
                logging.info("Found command '%s' at: %s", command, command_path)
            return str(command_path)

    if enable_logger:
        logging.warning("Command '%s' not found in search paths", command)
    return None


def build_customized_command(
    full_path_cmd: str,
    cmd_config: dict,
    enable_logger: bool = False,
) -> str:
    """
    A handy utility function to construct a command string with
    library paths and environment variables.

    Args:
        full_path_cmd (str): The full path to the command to be executed.
        cmd_config (dict): A dictionary containing environment variable names as keys
                           and their corresponding values. The special key
                           "LD_LIBRARY_PATH" can be used to specify a list of library paths.
        enable_logger (bool): If True, logs the constructed command.

    Input:
        full_path_cmd = "/usr/bin/foo"
        cmd_config = {
            "LD_LIBRARY_PATH": ["/path/to/lib1"],
            "env1": "value1",
            "env2": "value2",
        }
    Returns:
        'LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" env1="value1" env2="value2" /usr/bin/foo'
    """
    if not isinstance(full_path_cmd, str):
        raise TypeError("full_path_cmd must be a string type")

    if not Path(full_path_cmd).is_absolute():
        raise TypeError("full_path_cmd must be an absolute path")

    if not isinstance(cmd_config, dict):
        raise TypeError("config must be a dictionary")

    command_parts = []
    # Handle LD_LIBRARY_PATH before other environment variables to make sure it is prepended correctly
    ld_library_path = cmd_config.get("LD_LIBRARY_PATH")
    logging.debug("LD_LIBRARY_PATH: %s", ld_library_path)
    if ld_library_path:
        if not isinstance(ld_library_path, (list, tuple)):
            raise ValueError("cmd_config['LD_LIBRARY_PATH'] must be a list of strings")
        if any(not isinstance(path, str) for path in ld_library_path):
            raise ValueError("cmd_config['LD_LIBRARY_PATH'] must be a list of strings")

        lib_str = ":".join(ld_library_path)
        command_parts.append(f'LD_LIBRARY_PATH="{lib_str}:$LD_LIBRARY_PATH"')

    # Handle other environment variables
    for key, value in cmd_config.items():
        if key == "LD_LIBRARY_PATH":
            continue
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("cmd_config must map env names to string values")
        command_parts.append(f'{key}="{value}"')

    command_parts.append(full_path_cmd.strip())
    cmd = " ".join(command_parts)
    if enable_logger:
        logging.info("Constructed command: %s", cmd)

    return cmd


def resolve_executable_commands(
    default_commands: List[str],
    executable_json_path: str = "",
    enable_logger: bool = False,
) -> Optional[Dict[str, str]]:
    """Resolve multiple commands using executable JSON mapping and fallbacks.
    
        Args:
            default_commands (List[str]): A list of default command names to resolve.
            executable_json_path (str): Path to the JSON file containing command mappings.
            enable_logger (bool): If True, logs the resolution process.

        Example:
            default_commands = ["foo", "bar"]  # It can be a mix of full paths and command names.
            executable_json_path = "path/to/executable.json"
            # Suppose the executable.json content looks like this:
                {
                    "foo": {
                        "LD_PATH": ["/path/to/lib1"],
                        "env1": "value1",
                    }
                }
            Returns:
                {
                    "foo": "LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" env1="value1" /usr/bin/foo",
                    "bar": "/usr/bin/bar"
                }
    """
    if not default_commands:
        raise ValueError("default_commands must not be empty")
    if any(not command for command in default_commands):
        raise ValueError("default_commands must contain non-empty strings")

    unique_commands = list(dict.fromkeys(default_commands))

    # No custom mapping path means default command strings are used.
    if executable_json_path is None or not executable_json_path.strip():
        return resolve_default_commands(unique_commands)

    data = load_json_file(executable_json_path, enable_logger=enable_logger)
    # Empty or missing mapping file means no remapping is needed.
    if not data:
        return resolve_default_commands(unique_commands)

    resolved_commands = {}

    for default_command in unique_commands:
        command = build_customized_command(
            full_path_cmd=find_full_path_of_binary(default_command),
            cmd_config=data.get(Path(default_command).name, {}),    # Get the specific command configuration from the JSON data
            enable_logger=enable_logger,
        )
        if command is None:
            return None
        resolved_commands[default_command] = command

    if enable_logger:
        logging.info("Resolved customized commands: %s", resolved_commands)

    return resolved_commands


def resolve_default_commands(
    default_commands: List[str],
    enable_logger: bool = False,
) -> Dict[str, str]:
    """Resolve a list of default commands and build the full path to them.
    
        Example:
            default_commands = ["foo", "bar"]
            Returns:
                {
                    "foo": "/usr/bin/foo",
                    "bar": "/usr/bin/bar"
                }
    """
    resolved_commands: Dict[str, str] = {}
    for default_command in default_commands:
        resolved_commands[default_command] = find_full_path_of_binary(default_command)
    if enable_logger:
        logging.info("Resolved default commands: %s", resolved_commands)
    return resolved_commands
