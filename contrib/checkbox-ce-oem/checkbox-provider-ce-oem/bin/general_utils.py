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
