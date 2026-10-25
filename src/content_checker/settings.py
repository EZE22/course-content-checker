"""Load and validate the settings file."""

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_KEYS = ("content_folder", "rules", "required_sections")
FILE_KINDS = ("article", "lab")


class SettingsError(Exception):
    """A settings problem. The command line maps this to exit code 2."""


@dataclass(frozen=True)
class Settings:
    """Validated settings. content_folder is an absolute path to an existing folder."""

    content_folder: Path
    rules: list[str]
    required_sections: dict[str, list[str]]


def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def load_settings(path, known_rules):
    """Read the settings file at path and return a Settings, or raise SettingsError.

    A relative content_folder resolves against the folder holding the settings file.
    Rule names are checked against known_rules.
    """
    path = Path(path)

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SettingsError(f"Cannot read settings file {path}: {error}") from error

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise SettingsError(f"Settings file {path} is not valid JSON: {error}") from error

    if not isinstance(data, dict):
        raise SettingsError(f"Settings file {path} must contain a JSON object at the top level")

    for key in REQUIRED_KEYS:
        if key not in data:
            raise SettingsError(f"Settings key {key} is missing")

    content_folder = data["content_folder"]
    rules = data["rules"]
    required_sections = data["required_sections"]

    if not isinstance(content_folder, str):
        raise SettingsError("Settings key content_folder must be a path string")
    if not _is_str_list(rules):
        raise SettingsError("Settings key rules must be a list of rule name strings")
    if not isinstance(required_sections, dict):
        raise SettingsError("Settings key required_sections must be an object")
    for kind in FILE_KINDS:
        if kind not in required_sections:
            raise SettingsError(f"Settings key required_sections is missing the key {kind}")
        if not _is_str_list(required_sections[kind]):
            raise SettingsError(
                f"Settings key required_sections.{kind} must be a list of heading name strings"
            )

    for rule in rules:
        if rule not in known_rules:
            raise SettingsError(f"Settings key rules names an unknown rule: {rule}")

    folder = (path.parent / content_folder).resolve()
    if not folder.is_dir():
        raise SettingsError(f"Settings key content_folder is not an existing folder: {folder}")

    return Settings(
        content_folder=folder,
        rules=list(rules),
        required_sections={kind: list(required_sections[kind]) for kind in FILE_KINDS},
    )
