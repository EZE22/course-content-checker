import json
import re

import pytest
from content_checker.settings import Settings, SettingsError, load_settings

KNOWN_RULES = ["em_dash", "table_pipe", "missing_section", "table_lead_in"]


def write_settings(folder, **overrides):
    """Write a valid settings.json into folder, with any keys replaced or removed (None)."""
    (folder / "content").mkdir(exist_ok=True)
    data = {
        "content_folder": str(folder / "content"),
        "rules": ["em_dash", "table_pipe"],
        "required_sections": {"article": ["Overview"], "lab": ["Goal", "Steps"]},
    }
    for key, value in overrides.items():
        if value is None:
            del data[key]
        else:
            data[key] = value
    path = folder / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_valid_settings_load(tmp_path):
    path = write_settings(tmp_path)

    settings = load_settings(path, KNOWN_RULES)

    assert isinstance(settings, Settings)
    assert settings.content_folder.is_absolute()
    assert settings.content_folder.resolve() == (tmp_path / "content").resolve()
    assert settings.rules == ["em_dash", "table_pipe"]
    assert settings.required_sections == {"article": ["Overview"], "lab": ["Goal", "Steps"]}


def test_relative_content_folder_resolves_against_settings_file(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    (config / "course").mkdir()
    path = write_settings(config, content_folder="course")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    settings = load_settings(path, KNOWN_RULES)

    assert settings.content_folder.is_absolute()
    assert settings.content_folder.resolve() == (config / "course").resolve()


def test_missing_settings_file_names_the_path(tmp_path):
    path = tmp_path / "nope.json"

    with pytest.raises(SettingsError, match=re.escape(str(path))):
        load_settings(path, KNOWN_RULES)


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SettingsError, match=r"(?i)json"):
        load_settings(path, KNOWN_RULES)


@pytest.mark.parametrize("text", ["[]", '"text"', "42", "null"])
def test_top_level_not_an_object_raises(tmp_path, text):
    path = tmp_path / "settings.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(SettingsError, match=r"(?i)object"):
        load_settings(path, KNOWN_RULES)


@pytest.mark.parametrize("key", ["content_folder", "rules", "required_sections"])
def test_missing_key_names_the_key(tmp_path, key):
    path = write_settings(tmp_path, **{key: None})

    with pytest.raises(SettingsError, match=key):
        load_settings(path, KNOWN_RULES)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("content_folder", 5),
        ("content_folder", ["content"]),
        ("rules", "em_dash"),
        ("rules", [1, 2]),
        ("rules", ["em_dash", 3]),
        ("required_sections", ["article", "lab"]),
        ("required_sections", "article"),
    ],
)
def test_wrong_value_type_names_the_key(tmp_path, key, value):
    path = write_settings(tmp_path, **{key: value})

    with pytest.raises(SettingsError, match=key):
        load_settings(path, KNOWN_RULES)


@pytest.mark.parametrize(
    ("sections", "key"),
    [
        ({"lab": ["Goal"]}, "article"),
        ({"article": ["Overview"]}, "lab"),
        ({"article": "Overview", "lab": ["Goal"]}, "article"),
        ({"article": ["Overview"], "lab": "Goal"}, "lab"),
        ({"article": [1], "lab": ["Goal"]}, "article"),
        ({"article": ["Overview"], "lab": ["Goal", None]}, "lab"),
    ],
)
def test_bad_required_sections_entry_names_the_key(tmp_path, sections, key):
    path = write_settings(tmp_path, required_sections=sections)

    with pytest.raises(SettingsError, match=key):
        load_settings(path, KNOWN_RULES)


def test_unknown_rule_name_is_named(tmp_path):
    path = write_settings(tmp_path, rules=["em_dash", "heading_skip"])

    with pytest.raises(SettingsError, match="heading_skip"):
        load_settings(path, KNOWN_RULES)


def test_missing_content_folder_names_the_key(tmp_path):
    path = write_settings(tmp_path, content_folder=str(tmp_path / "gone"))

    with pytest.raises(SettingsError, match="content_folder"):
        load_settings(path, KNOWN_RULES)
