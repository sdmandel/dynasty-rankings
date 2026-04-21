"""Normalize display names across public JSON payloads using team_registry.json."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TARGET_FILES = [
    "transactions.json",
    "feed.json",
    "closers.json",
    "prospects.json",
    "franchises.json",
    "managers.json",
    "league_intelligence.json",
    "standings.json",
    "rivalries.json",
    "rules.json",
    "weekly_player_heat.json",
]


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_alias_map() -> dict[str, str]:
    data = load_json(DATA_DIR / "team_registry.json")
    mapping: dict[str, str] = {}
    for row in data.get("teams", []):
        display = row["display_name"]
        for alias in row.get("aliases", []):
            if alias != display:
                mapping[alias] = display
    return mapping


def normalize(value: object, mapping: dict[str, str]) -> object:
    if isinstance(value, dict):
        out: dict[object, object] = {}
        for key, item in value.items():
            new_key = mapping.get(key, key) if isinstance(key, str) else key
            out[new_key] = normalize(item, mapping)
        return out
    if isinstance(value, list):
        return [normalize(item, mapping) for item in value]
    if isinstance(value, str):
        text = value
        for alias, display in mapping.items():
            text = text.replace(alias, display)
        return text
    return value


def main() -> None:
    mapping = load_alias_map()
    for name in TARGET_FILES:
        path = DATA_DIR / name
        data = load_json(path)
        normalized = normalize(data, mapping)
        path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
