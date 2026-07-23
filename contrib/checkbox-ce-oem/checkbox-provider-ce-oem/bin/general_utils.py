import json
import os
import logging

PLAINBOX_PROVIDER_DATA = os.getenv("PLAINBOX_PROVIDER_DATA", "")


def load_json_file(json_file_path: str, enable_logger: bool = False) -> dict:
    """Load a JSON file, preferring the provider data directory if set."""
    def _load(path: str):
        try:
            if enable_logger:
                logging.info(f"Attempting to load JSON file: {path}")
            with open(path, "r", encoding="utf-8") as file_obj:
                return json.load(file_obj)
        except (FileNotFoundError, PermissionError, json.JSONDecodeError, OSError):
            if enable_logger:
                logging.warning(f"Failed to load JSON file: {path}")
            return None

    f_path = json_file_path
    # Try provider data directory first if applicable.
    if PLAINBOX_PROVIDER_DATA:
        f_path = os.path.join(PLAINBOX_PROVIDER_DATA, json_file_path)

    data = _load(f_path)
    if data is not None:
        return data

    return {}


def build_command(config: dict, enable_logger: bool = False) -> str:
    """
        A handy utility function to construct a command string with environment variables and library paths.
    
        Example 1:
            
            config = {
                "bin": "snap.foo.bar",
                "lib_paths": ["/path/to/lib1", "/path/to/lib2"],
                "env": {
                    "VAR1": "value1",
                    "VAR2": "value2"
                }
            }

            You will get the command string as follows:
                'LD_LIBRARY_PATH="/path/to/lib1:/path/to/lib2:$LD_LIBRARY_PATH" VAR1="value1" VAR2="value2" snap.'

        Example 2:

            config = {
                "bin": "foo.bar",
                "lib_paths": [],
                "env": {
                    "VAR1": "value1"
                }
            }

            You will get the command string as follows:
                'VAR1="value1" foo.bar'
    """
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary")

    command = config.get("bin")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("config['bin'] must be a non-empty string")

    env_vars = []
    lib_paths = config.get("lib_paths")
    if lib_paths:
        if not isinstance(lib_paths, (list, tuple)):
            raise ValueError("config['lib_paths'] must be a list of strings")

        lib_str = ":".join(lib_paths)
        env_vars.append(f'LD_LIBRARY_PATH="{lib_str}:$LD_LIBRARY_PATH"')

    env = config.get("env", {})
    if env is None:
        env = {}
    if not isinstance(env, dict):
        raise ValueError("config['env'] must be a dictionary")

    for key, value in env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("config['env'] must map strings to strings")
        env_vars.append(f'{key}="{value}"')

    cmd = " ".join([*env_vars, command])
    if enable_logger:
        logging.info(f"Constructed command: {cmd}")

    return cmd
    