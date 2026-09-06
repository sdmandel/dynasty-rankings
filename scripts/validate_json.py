"""Validate every public JSON payload, including history buckets."""
import json
from pathlib import Path


def main():
    paths = list(Path("data").rglob("*.json"))
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))
    print(f"OK: {len(paths)} JSON files valid")


if __name__ == "__main__":
    main()
