"""
build_dynasty_rankings.py — Build static JSON data for the dynasty rankings site page.

Reads:
  /Users/stevemandella/Documents/Making/fantrax/data/dynasty_history.json
  /Users/stevemandella/Documents/Making/fantrax/data/rankings_latest.csv

Writes to powerrankings/data/:
  dynasty_rankings_latest.json  — current snapshot with rank_change and source ranks
  dynasty_player_trajectories.json — full rank history per player for modal chart

Run manually after each rankings update:
  python powerrankings/scripts/build_dynasty_rankings.py
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

_SUFFIX_RE         = re.compile(r"\b(Jr\.?|Sr\.?|II|III|IV|V)(?=\s|$)", re.IGNORECASE)
_PERIOD_RE         = re.compile(r"(?<=\b\w)\.")
_APOSTROPHE_RE     = re.compile(r"['’]")
_MIDDLE_INITIAL_RE = re.compile(r"(?<=\s)\b\w\b(?=\s)")


def _normalize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = _SUFFIX_RE.sub("", name)
    name = _PERIOD_RE.sub("", name)
    name = _APOSTROPHE_RE.sub("", name)
    name = " ".join(name.split())
    name = _MIDDLE_INITIAL_RE.sub("", name)
    return " ".join(name.split()).lower()

FANTRAX_DATA = Path("/Users/stevemandella/Documents/Making/fantrax/data")
SITE_DATA    = Path(__file__).resolve().parent.parent / "data"

HISTORY_PATH = FANTRAX_DATA / "dynasty_history.json"
CSV_PATH     = FANTRAX_DATA / "rankings_latest.csv"


def _load_history() -> list[dict]:
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def _load_csv() -> dict[str, dict]:
    """Return {normalized_name: row_dict} from rankings_latest.csv."""
    out: dict[str, dict] = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = _normalize(row.get("Player", ""))
            if name:
                out[name] = row
    return out


def _safe_int(val) -> int | None:
    try:
        return int(val) if val not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def build() -> None:
    history = _load_history()
    if not history:
        raise SystemExit("dynasty_history.json is empty")

    csv_by_name = _load_csv()

    latest   = history[-1]
    previous = history[-2] if len(history) >= 2 else None

    prev_ranks: dict[str, int] = {}
    if previous:
        for p in previous["rankings"]:
            prev_ranks[p["name"]] = p["rank"]

    # ── dynasty_rankings_latest.json ─────────────────────────────────────────

    rankings_out = []
    for entry in sorted(latest["rankings"], key=lambda e: e["rank"]):
        name         = entry["name"]
        display_name = entry["display_name"]
        csv_row      = csv_by_name.get(name, {})

        positions_raw = csv_row.get("Positions", "")
        positions     = [p.strip() for p in positions_raw.split(",") if p.strip()] if positions_raw else []

        prior = prev_ranks.get(name)
        rank_change = (prior - entry["rank"]) if prior else 0   # positive = moved up

        rankings_out.append({
            "rank":         entry["rank"],
            "display_name": display_name,
            "name":         name,
            "team":         csv_row.get("Team", ""),
            "positions":    positions,
            "age":          _safe_int(csv_row.get("Age")),
            "level":        csv_row.get("Level", ""),
            "score":        entry["score"],
            "hkb_rank":     _safe_int(entry.get("hkb_rank") or csv_row.get("HKB#")),
            "fp_rank":      _safe_int(entry.get("fp_rank")  or csv_row.get("FP#")),
            "ibw_rank":     _safe_int(entry.get("ibw_rank") or csv_row.get("IBW#")),
            "pl_rank":      _safe_int(entry.get("pl_rank")  or csv_row.get("PL#")),
            "fthq_rank":    _safe_int(entry.get("fthq_rank") or csv_row.get("FTHQ#")),
            "rank_change":  rank_change,
        })

    latest_json = {
        "generated": latest["date"],
        "rankings":  rankings_out,
    }
    out_path = SITE_DATA / "dynasty_rankings_latest.json"
    out_path.write_text(json.dumps(latest_json, indent=2), encoding="utf-8")
    print(f"Wrote {len(rankings_out)} players → {out_path}")

    # ── dynasty_player_trajectories.json ─────────────────────────────────────

    players: dict[str, dict] = {}
    for snapshot in history:
        snap_date = snapshot["date"]
        for entry in snapshot["rankings"]:
            name = entry["name"]
            if name not in players:
                players[name] = {
                    "display_name": entry["display_name"],
                    "current_rank":  None,
                    "current_score": None,
                    "points":        [],
                }
            players[name]["points"].append({
                "date":  snap_date,
                "rank":  entry["rank"],
                "score": entry["score"],
            })

    # Set current rank/score from latest snapshot
    for entry in latest["rankings"]:
        name = entry["name"]
        if name in players:
            players[name]["current_rank"]  = entry["rank"]
            players[name]["current_score"] = entry["score"]

    traj_json = {
        "generated": latest["date"],
        "players":   players,
    }
    traj_path = SITE_DATA / "dynasty_player_trajectories.json"
    traj_path.write_text(json.dumps(traj_json, indent=2), encoding="utf-8")
    print(f"Wrote {len(players)} player trajectories → {traj_path}")


if __name__ == "__main__":
    build()
