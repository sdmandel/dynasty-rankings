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


STATS_PATH      = SITE_DATA / "season_stats.json"
FG_ID_CACHE_PATH = FANTRAX_DATA / "fg_id_cache.json"


def _load_fg_id_cache() -> dict:
    if not FG_ID_CACHE_PATH.exists():
        return {}
    return json.loads(FG_ID_CACHE_PATH.read_text(encoding="utf-8"))


_PITCHER_POS = {"SP", "RP", "P", "SIRP", "MIRP"}

def _stat_type(positions: list[str]) -> str:
    return "pitching" if positions and all(p in _PITCHER_POS for p in positions) else "batting"


def _load_season_stats() -> tuple:
    if not STATS_PATH.exists():
        return {}, {}, {}, {}, None
    data = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    return (
        data.get("mlb_batting", {}),
        data.get("mlb_pitching", {}),
        data.get("milb_batting", {}),
        data.get("milb_pitching", {}),
        data.get("generated"),
    )


def build() -> None:
    history = _load_history()
    if not history:
        raise SystemExit("dynasty_history.json is empty")

    csv_by_name = _load_csv()
    fg_cache    = _load_fg_id_cache()
    mlb_bat, mlb_pit, milb_bat, milb_pit, stats_generated = _load_season_stats()

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

        def _sf(key, decimals=None):
            v = csv_row.get(key, "")
            if v in ("", None): return None
            try:
                f = float(v)
                return round(f, decimals) if decimals is not None else f
            except (ValueError, TypeError):
                return v

        fg_entry = fg_cache.get(name, {})
        rankings_out.append({
            "rank":         entry["rank"],
            "display_name": display_name,
            "name":         name,
            "fg_id":        fg_entry.get("fg_id"),
            "fg_stat_type": _stat_type(positions),
            "team":         csv_row.get("Team", ""),
            "positions":    positions,
            "age":          _safe_int(csv_row.get("Age")),
            "level":        csv_row.get("Level", ""),
            "score":        entry["score"],
            # Source ranks — prefer enriched history, fall back to CSV
            "hkb_rank":     _safe_int(entry.get("hkb_rank") or csv_row.get("HKB#")),
            "delta_hkb":    _safe_int(csv_row.get("Δ HKB")),
            "fp_rank":      _safe_int(entry.get("fp_rank")  or csv_row.get("FP#")),
            "delta_fp":     _safe_int(csv_row.get("Δ FP")),
            "ibw_rank":     _safe_int(entry.get("ibw_rank") or csv_row.get("IBW#")),
            "delta_ibw":    _safe_int(csv_row.get("Δ IBW")),
            "pl_rank":      _safe_int(entry.get("pl_rank")  or csv_row.get("PL#")),
            "fthq_rank":    _safe_int(entry.get("fthq_rank") or csv_row.get("FTHQ#")),
            "rank_change":  rank_change,
            # Analysis columns
            "proj_z":       _sf("Proj Z", 3),
            "hkb_value":    _sf("HKB Value"),
            "owned_by":     csv_row.get("Owned By", "") or "",
            "eta":          csv_row.get("ETA", "") or "",
            "reason":       csv_row.get("Reason", "") or "",
            # Steamer batting
            "st_hr":        _sf("St HR"),
            "st_r":         _sf("St R"),
            "st_rbi":       _sf("St RBI"),
            "st_sb":        _sf("St SB"),
            "st_ops":       _sf("St OPS", 3),
            "zips_hr":      _sf("Zips HR"),
            "zips_ops":     _sf("Zips OPS", 3),
            # Steamer pitching
            "st_qs":        _sf("St QS"),
            "st_k":         _sf("St K"),
            "st_era":       _sf("St ERA", 2),
            "st_svh":       _sf("St SVH"),
            "st_whip":      _sf("St WHIP", 3),
            "zips_era":     _sf("Zips ERA", 2),
            "zips_k":       _sf("Zips K"),
            # MLB season stats
            **(lambda b, pi: {
                "mlb_hr":   b.get("hr"),  "mlb_r":   b.get("r"),
                "mlb_rbi":  b.get("rbi"), "mlb_sb":  b.get("sb"),
                "mlb_ops":  b.get("ops"), "mlb_pa":  b.get("pa"),
                "mlb_qs":   pi.get("qs"), "mlb_k":   pi.get("k"),
                "mlb_era":  pi.get("era"),"mlb_svh": pi.get("svh"),
                "mlb_whip": pi.get("whip"),"mlb_ip": pi.get("ip"),
            })(mlb_bat.get(name, {}), mlb_pit.get(name, {})),
            # MiLB season stats (no QS — minor leagues don't track it)
            **(lambda b, pi: {
                "milb_hr":   b.get("hr"),  "milb_r":   b.get("r"),
                "milb_rbi":  b.get("rbi"), "milb_sb":  b.get("sb"),
                "milb_ops":  b.get("ops"), "milb_pa":  b.get("pa"),
                "milb_k":    pi.get("k"),  "milb_era": pi.get("era"),
                "milb_svh":  pi.get("svh"),"milb_whip":pi.get("whip"),
                "milb_ip":   pi.get("ip"),
            })(milb_bat.get(name, {}), milb_pit.get(name, {})),
        })

    latest_json = {
        "generated":       latest["date"],
        "stats_generated": stats_generated,
        "rankings":        rankings_out,
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
