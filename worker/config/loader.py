"""
Config loader — merges sources in priority order:
  1. CLI arguments   (highest)
  2. Environment variables
  3. config.ini file
  4. Defaults        (lowest)
"""
import os
import configparser
from .defaults import DEFAULTS, ENV_MAP


def load_config(args=None, config_file="config.ini") -> dict:
    """
    Load and merge configuration from all sources.

    Args:
        args: argparse.Namespace from CLI (or None)
        config_file: path to INI file (or None to skip)

    Returns:
        Merged config dict with correct Python types.
    """
    config = dict(DEFAULTS)

    # 1 — config.ini
    if config_file and os.path.exists(config_file):
        parser = configparser.ConfigParser()
        parser.read(config_file)
        section = parser["ollabridge"] if "ollabridge" in parser else {}
        for key in DEFAULTS:
            if key in section:
                config[key] = _cast(key, section[key])

    # 2 — Environment variables
    for key, env_var in ENV_MAP.items():
        val = os.environ.get(env_var)
        if val is not None:
            config[key] = _cast(key, val)

    # 3 — CLI args (highest priority; only non-None values override)
    if args:
        for key in DEFAULTS:
            val = getattr(args, key, None)
            if val is not None:
                config[key] = val

    return config


def save_config(config: dict, config_file="config.ini"):
    """Persist config to an INI file (omits None values)."""
    parser = configparser.ConfigParser()
    parser["ollabridge"] = {}
    for key, val in config.items():
        if val is not None:
            parser["ollabridge"][key] = str(val)
    with open(config_file, "w") as f:
        parser.write(f)


def _cast(key: str, value: str):
    """Cast a raw string to the correct Python type based on the default."""
    default = DEFAULTS.get(key)
    if isinstance(default, bool):
        return str(value).lower() in ("true", "1", "yes", "on")
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value
