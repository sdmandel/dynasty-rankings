"""
build_dynasty_rankings.py — Build static JSON data for the dynasty rankings site page.

Reads:
  /Users/stevemandella/Documents/Making/fantrax/data/dynasty_history.json
  /Users/stevemandella/Documents/Making/fantrax/data/rankings_latest.csv
  /Users/stevemandella/Documents/Making/fantrax/data/ownership_cache.json  (optional, hourly)

Writes to powerrankings/data/:
  dynasty_rankings_latest.json  — current snapshot with rank_change and source ranks
  dynasty_player_trajectories.json — full rank history per player for modal chart
  rosters.json                  — compact {team → players} for agent/tool use

Run manually after each rankings update:
  python powerrankings/scripts/build_dynasty_rankings.py
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import unicodedata
from collections import defaultdict
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

FANTRAX_DATA = Path(__file__).resolve().parent.parent.parent / "data"
SITE_DATA    = Path(__file__).resolve().parent.parent / "data"

HISTORY_PATH        = FANTRAX_DATA / "dynasty_history.json"
CSV_PATH            = FANTRAX_DATA / "rankings_latest.csv"
OWNERSHIP_CACHE_PATH = FANTRAX_DATA / "ownership_cache.json"


def _load_history(path=None) -> list[dict]:
    return json.loads((path or HISTORY_PATH).read_text(encoding="utf-8"))


def _load_ownership_cache(path=None) -> dict[str, str]:
    """Return {normalized_name: team_name} from the hourly ownership cache, or {}."""
    path = path or OWNERSHIP_CACHE_PATH
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {_normalize(name): team for name, team in raw.get("owners", {}).items()}
    except (json.JSONDecodeError, KeyError):
        return {}


def _load_csv(path=None) -> dict[str, dict]:
    """Return {normalized_name: row_dict} from rankings_latest.csv."""
    out: dict[str, dict] = {}
    with open(path or CSV_PATH, newline="", encoding="utf-8") as f:
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


def _load_fg_id_cache(path=None) -> dict:
    path = path or FG_ID_CACHE_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


_PITCHER_POS = {"SP", "RP", "P", "SIRP", "MIRP"}

def _stat_type(positions: list[str]) -> str:
    return "pitching" if positions and all(p in _PITCHER_POS for p in positions) else "batting"


def _load_season_stats(path=None) -> tuple:
    path = path or STATS_PATH
    if not path.exists():
        return {}, {}, {}, {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    return (
        data.get("mlb_batting", {}),
        data.get("mlb_pitching", {}),
        data.get("milb_batting", {}),
        data.get("milb_pitching", {}),
        data.get("generated"),
    )


BUILD_API_VERSION = 2


def build(*, source_data=None, site_data=None) -> None:
    source_data = source_data or FANTRAX_DATA
    site_data = site_data or SITE_DATA
    history = _load_history(source_data / "dynasty_history.json")
    if not history:
        raise SystemExit("dynasty_history.json is empty")

    csv_by_name    = _load_csv(source_data / "rankings_latest.csv")
    fg_cache       = _load_fg_id_cache(source_data / "fg_id_cache.json")
    ownership_cache = _load_ownership_cache(source_data / "ownership_cache.json")
    mlb_bat, mlb_pit, milb_bat, milb_pit, stats_generated = _load_season_stats(site_data / "season_stats.json")

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
            "owned_by":     ownership_cache.get(name) or csv_row.get("Owned By", "") or "",
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
                "mlb_hr":     b.get("hr"),   "mlb_r":     b.get("r"),
                "mlb_rbi":    b.get("rbi"),  "mlb_sb":    b.get("sb"),
                "mlb_ops":    b.get("ops"),  "mlb_pa":    b.get("pa"),
                "mlb_ab":     b.get("ab"),   "mlb_bat_gp":b.get("gp"),
                "mlb_qs":     pi.get("qs"),  "mlb_k":     pi.get("k"),
                "mlb_era":    pi.get("era"), "mlb_svh":   pi.get("svh"),
                "mlb_whip":   pi.get("whip"),"mlb_ip":    pi.get("ip"),
                "mlb_pit_gp": pi.get("gp"),
            })(mlb_bat.get(name, {}), mlb_pit.get(name, {})),
            # MiLB season stats (no QS — minor leagues don't track it)
            **(lambda b, pi: {
                "milb_hr":     b.get("hr"),  "milb_r":   b.get("r"),
                "milb_rbi":    b.get("rbi"), "milb_sb":  b.get("sb"),
                "milb_ops":    b.get("ops"), "milb_pa":  b.get("pa"),
                "milb_ab":     b.get("ab"),
                "milb_k":      pi.get("k"),  "milb_era": pi.get("era"),
                "milb_svh":    pi.get("svh"),"milb_whip":pi.get("whip"),
                "milb_ip":     pi.get("ip"), "milb_pit_gp": pi.get("gp"),
            })(milb_bat.get(name, {}), milb_pit.get(name, {})),
        })

    # ── Inject draft pick rows ────────────────────────────────────────────────
    picks_path = source_data / "draft_picks.json"
    if picks_path.exists():
        pick_data = json.loads(picks_path.read_text(encoding="utf-8"))
        _null_stats = {k: None for k in (
            "fg_id", "fg_stat_type", "team", "age", "delta_hkb", "fp_rank", "delta_fp",
            "ibw_rank", "delta_ibw", "pl_rank", "fthq_rank", "rank_change",
            "proj_z", "eta", "reason",
            "st_hr", "st_r", "st_rbi", "st_sb", "st_ops", "zips_hr", "zips_ops",
            "st_qs", "st_k", "st_era", "st_svh", "st_whip", "zips_era", "zips_k",
            "mlb_hr", "mlb_r", "mlb_rbi", "mlb_sb", "mlb_ops", "mlb_pa", "mlb_ab",
            "mlb_bat_gp", "mlb_qs", "mlb_k", "mlb_era", "mlb_svh", "mlb_whip",
            "mlb_ip", "mlb_pit_gp",
            "milb_hr", "milb_r", "milb_rbi", "milb_sb", "milb_ops", "milb_pa",
            "milb_ab", "milb_k", "milb_era", "milb_svh", "milb_whip", "milb_ip",
            "milb_pit_gp",
        )}
        for pk in pick_data:
            rankings_out.append({
                "rank":         None,          # assigned below after sort
                "display_name": pk["display_name"],
                "name":         pk["display_name"],
                "positions":    pk["positions"],
                "level":        "PICK",
                "score":        pk["score"],
                "hkb_rank":     pk.get("hkb_rank"),
                "hkb_value":    pk.get("hkb_value"),
                "owned_by":     pk.get("owned_by", ""),
                **_null_stats,
            })
        # Re-sort by score and re-assign ranks
        rankings_out.sort(key=lambda r: r["score"] or 0, reverse=True)
        for i, row in enumerate(rankings_out, 1):
            row["rank"] = i
        print(f"Injected {len(pick_data)} pick rows → {len(rankings_out)} total")

    latest_json = {
        "generated":       latest["date"],
        "stats_generated": stats_generated,
        "rankings":        rankings_out,
    }
    owner_path = source_data / "ownership_cache.json"
    latest_json["source_dates"] = {"rankings": latest["date"], "stats": stats_generated,
        "ownership": json.loads(owner_path.read_text()).get("generated_at") if owner_path.exists() else None}
    out_path = site_data / "dynasty_rankings_latest.json"
    out_path.write_text(json.dumps(latest_json, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(rankings_out)} rows → {out_path}")

    # ── rosters.json — compact per-team roster for agent/tool use ─────────────
    roster_map: dict[str, list] = defaultdict(list)
    for row in rankings_out:
        owner = row.get("owned_by") or ""
        if owner:
            roster_map[owner].append({
                "name":      row["display_name"],
                "rank":      row["rank"],
                "score":     row["score"],
                "age":       row["age"],
                "level":     row["level"],
                "positions": row["positions"],
            })
    rosters_json = {
        "generated":  latest["date"],
        "teams": [
            {"team": team, "players": sorted(players, key=lambda p: p["rank"] or 9999)}
            for team, players in sorted(roster_map.items())
        ],
    }
    rosters_json["source_dates"] = latest_json["source_dates"]
    rosters_path = site_data / "rosters.json"
    rosters_path.write_text(json.dumps(rosters_json, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(roster_map)} team rosters → {rosters_path}")

    # ── dynasty_player_trajectories.json ─────────────────────────────────────

    history_hash = hashlib.sha256((source_data / "dynasty_history.json").read_bytes() + Path(__file__).read_bytes()).hexdigest()
    manifest_path = site_data / "dynasty_player_trajectories.manifest.json"
    if manifest_path.exists() and (site_data / "dynasty_player_trajectories.json").exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("source_hash") == history_hash:
            print("Unchanged dynasty history; reused published buckets")
            return

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
        "source_hash": history_hash,
        "players":   players,
    }
    traj_path = site_data / "dynasty_player_trajectories.json"
    traj_path.write_text(json.dumps(traj_json, separators=(",", ":")), encoding="utf-8")
    helper_path = Path(__file__).with_name("build_history_shards.py")
    spec = importlib.util.spec_from_file_location("history_shards", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.write_history_shards(site_data.parent, "dynasty_player_trajectories", traj_json)
    print(f"Wrote {len(players)} player trajectories → {traj_path}")


if __name__ == "__main__":
    build()
