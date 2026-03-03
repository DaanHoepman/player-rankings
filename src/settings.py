# src/settings.py

import yaml

from pathlib import Path
from typing import Dict

#------------------------------------------------------------

def _deep_merge(base: Dict, override: Dict) -> None:
    """
    Recursively merges the override dictionary into the base dictionary. 
    If a key exists in both dictionaries and both values are dictionaries, they will be merged recursively. 
    Otherwise, the value from the override dictionary will overwrite the value in the base dictionary.

    Parameters
    ----------
    base: Dict
        The base dictionary that will be updated with values from the override dictionary.
    override: Dict
        The dictionary containing values that will override those in the base dictionary.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_config(default: str = "config/default.yaml", local: str = "config/local.yaml") -> Dict:
    """
    Loads the configuration from the default YAML file and optionally overrides it with values from a local YAML file.

    Parameters
    ----------
    default: str
        The path to the default configuration YAML file. Default is "config/default.yaml".
    local: str
        The path to the local configuration YAML file. If this file exists, its values will override those in the default configuration. Default is "config/local.yaml".
    
    Returns
    -------
    Dict
        The merged configuration dictionary containing values from the default configuration overridden by any values from the local configuration.
    """
    default_path = Path(default)
    if not default_path.exists():
        raise FileNotFoundError(f"Default config file not found at {default_path}")
    
    with open(default_path) as f:
        config = yaml.safe_load(f)

    local_path = Path(local)
    if local_path.exists():
        with open(local_path) as f:
            local_overrides = yaml.safe_load(f)
        if local_overrides:
            _deep_merge(config, local_overrides)

    return config
