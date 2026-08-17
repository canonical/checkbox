import json
import logging
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List


def load_json_file(
    json_file_path: str,
    enable_logger: bool = False,
) -> Dict[str, Any]:
    """Load a JSON file and return its contents as a dictionary.

    Does not raise exceptions for missing or unreadable files.
    Instead, it returns an empty dictionary. Let the caller handle
    the case of an empty dictionary if needed.
    """

    if not json_file_path or not isinstance(json_file_path, str):
        if enable_logger:
            logging.warning(
                "Empty JSON file path provided, returning empty dictionary"
            )
        return {}

    resolved_path = os.path.join(
        os.getenv("PLAINBOX_PROVIDER_DATA", ""), json_file_path
    )
    if not Path(resolved_path).exists():
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


def find_full_path_of_binary(
    command: str,
    enable_logger: bool = False,
) -> str:
    """Find the full path of a command using the predefined priority order.

    Args:
        command: The command name to search for.

    Returns:
        The absolute path of the command if found, otherwise an empty string.
    """
    search_paths = (
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/sbin"),
        Path("/sbin"),
        Path("/usr/local/bin"),
        Path("/usr/local/sbin"),
        Path("/snap/bin"),
    )

    if Path(command).is_absolute() and Path(command).is_file():
        if enable_logger:
            logging.info(
                "Command '%s' is an absolute path and exists", command
            )
        return command

    for directory in search_paths:
        command_path = directory / command

        if command_path.is_file() and command_path.stat().st_mode & 0o111:
            if enable_logger:
                logging.info(
                    "Found command '%s' at: %s", command, command_path
                )
            return str(command_path)

    if enable_logger:
        logging.warning("Command '%s' not found in search paths", command)
    return ""


def build_customized_command(
    full_path_cmd: str,
    cmd_config: dict,
    enable_logger: bool = False,
) -> str:
    """Construct a command string with optional environment variables
    and library paths.

    Args:
        full_path_cmd (str): Full path to the command to be executed.
        cmd_config (dict): A dictionary containing environment variable
                           names as keys and their corresponding values.
                           The special key "LD_LIBRARY_PATH" can be used
                           to specify a list of library paths.
        enable_logger (bool): If True, logs the constructed command.

    Input:
        full_path_cmd = "/usr/bin/foo"
        cmd_config = {
            "LD_LIBRARY_PATH": ["/path/to/lib1"],
            "env1": "value1",
            "env2": "value2",
        }
    Returns:
        A shell command string.
    """
    if not isinstance(full_path_cmd, str):
        raise TypeError("full_path_cmd must be a string type")

    full_path_cmd = full_path_cmd.strip()

    if not (
        Path(full_path_cmd).is_file()
        and Path(full_path_cmd).stat().st_mode & 0o111
    ):
        raise TypeError(
            "full_path_cmd must be an absolute path to an executable file"
        )

    if not isinstance(cmd_config, dict):
        raise TypeError("config must be a dictionary")

    command_parts = []
    # Handle LD_LIBRARY_PATH before other environment variables to make
    # sure it is prepended correctly.
    ld_library_path = cmd_config.get("LD_LIBRARY_PATH")
    logging.debug("LD_LIBRARY_PATH: %s", ld_library_path)
    if ld_library_path:
        if not isinstance(ld_library_path, (list, tuple)):
            raise ValueError(
                "cmd_config['LD_LIBRARY_PATH'] must be a list of strings"
            )
        if any(not isinstance(path, str) for path in ld_library_path):
            raise ValueError(
                "cmd_config['LD_LIBRARY_PATH'] must be a list of strings"
            )

        lib_str = ":".join(ld_library_path)
        command_parts.append(f'LD_LIBRARY_PATH="{lib_str}:$LD_LIBRARY_PATH"')

    # Handle other environment variables
    for key, value in cmd_config.items():
        if key == "LD_LIBRARY_PATH":
            continue
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("cmd_config must map env names to string values")
        command_parts.append(f'{key}="{value}"')

    command_parts.append(full_path_cmd)
    cmd = " ".join(command_parts)
    if enable_logger:
        logging.info("Constructed command: %s", cmd)

    return cmd


def resolve_executable_commands(
    default_commands: List[str],
    enable_logger: bool = False,
) -> Dict[str, str]:
    """Resolve command strings using optional JSON-based customization.

    Args:
        default_commands (List[str]): Default command names to resolve.
        enable_logger (bool): If True, logs the resolution process.

    Example:
        # It can be a mix of full paths and command names.
        default_commands = ["foo", "bar"]
        # Suppose the executable.json content looks like this:
            {
                "foo": {
                    "LD_PATH": ["/path/to/lib1"],
                    "env1": "value1",
                }
            }
        Returns:
            {
                "foo": "LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" env1="value1" /usr/bin/foo",   # noqa E501
                "bar": "/usr/bin/bar"
            }
    """
    if not default_commands:
        raise ValueError("default_commands must not be empty")
    if any(not command for command in default_commands):
        raise ValueError("default_commands must contain non-empty strings")

    unique_commands = list(dict.fromkeys(default_commands))

    executable_json_path = os.environ.get("EXECUTABLE_JSON_PATH", "").strip()

    # No custom mapping path means default command strings are used.
    if not executable_json_path:
        return resolve_default_commands(unique_commands)

    data = load_json_file(executable_json_path, enable_logger=enable_logger)
    # Empty or missing mapping file means no need to customize commands.
    if not data:
        return resolve_default_commands(unique_commands)

    resolved_commands = {}

    for default_command in unique_commands:
        command = build_customized_command(
            full_path_cmd=find_full_path_of_binary(default_command),
            cmd_config=data.get(Path(default_command).name, {}),
            enable_logger=enable_logger,
        )
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
        resolved_commands[default_command] = find_full_path_of_binary(
            default_command
        )
    if enable_logger:
        logging.info("Resolved default commands: %s", resolved_commands)
    return resolved_commands


def with_resolved_commands(
    default_commands: List[str],
    inject_param: str = "resolved_commands",
    enable_logger: bool = True,
    strict: bool = True,
) -> Callable:
    """Inject resolved command mapping into a wrapped function.

    The command mapping is always resolved from the current environment,
    including ``EXECUTABLE_JSON_PATH`` when it is present.

    Args:
        default_commands: Command names to resolve.
        inject_param: Keyword argument name used for injection.
        enable_logger: If True, enable resolver logging.
        strict: If True, raise ValueError when any command is unresolved.

    Returns:
        A decorator that injects ``{command: resolved_command}`` mapping.
    """
    if not default_commands:
        raise ValueError("default_commands must not be empty")
    if any(not command for command in default_commands):
        raise ValueError("default_commands must contain non-empty strings")
    if not inject_param:
        raise ValueError("inject_param must not be empty")

    unique_commands = list(dict.fromkeys(default_commands))

    def _decorator(func: Callable) -> Callable:
        @wraps(func)
        def _wrapped(*args, **kwargs):
            resolved_commands = resolve_executable_commands(
                default_commands=unique_commands,
                enable_logger=enable_logger,
            )
            if strict:
                unresolved = [
                    command
                    for command in unique_commands
                    if not resolved_commands.get(command)
                ]
                if unresolved:
                    missing = ", ".join(unresolved)
                    raise ValueError(
                        f"Failed to resolve executable commands: {missing}"
                    )

            kwargs[inject_param] = resolved_commands
            return func(*args, **kwargs)

        return _wrapped

    return _decorator
