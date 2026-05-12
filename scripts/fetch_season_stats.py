"""
fetch_season_stats.py — MLB stats from FanGraphs + MiLB stats from milb_stats.json.

Writes powerrankings/data/season_stats.json with four dicts:
  mlb_batting, mlb_pitching, milb_batting, milb_pitching

A player who debuted and went back down will appear in both mlb_* and milb_* dicts.

Run from the fantrax venv:
  source /Users/stevemandella/Documents/Making/fantrax/.venv/bin/activate
  python powerrankings/scripts/fetch_season_stats.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/stevemandella/Documents/Making/fantrax")
from src.rankings.fangraphs import fetch_current_stats_batters, fetch_current_stats_pitchers
from src.shared.utils import normalize_name

SEASON = 2026
BOT_ROOT = Path(__file__).resolve().parent.parent.parent
MILB_STATS_PATH = BOT_ROOT / "data" / "milb_stats.json"
SITE_DATA = Path(__file__).resolve().parent.parent / "data"


def _si(v):
    return int(round(float(v))) if v not in (None, "") else None


def _sf(v, d):
    return round(float(v), d) if v not in (None, "") else None


def build() -> None:
    # MLB stats from FanGraphs — include any real appearance (1 PA / 0.1 IP)
    mlb_batting: dict[str, dict] = {}
    for row in fetch_current_stats_batters(SEASON):
        pa = float(row.get("PA") or 0)
        if pa < 1:
            continue
        key = normalize_name(row.get("player_name", ""))
        if not key:
            continue
        mlb_batting[key] = {
            "hr":  _si(row.get("HR")),
            "r":   _si(row.get("R")),
            "rbi": _si(row.get("RBI")),
            "sb":  _si(row.get("SB")),
            "ops": _sf(row.get("OPS"), 3),
            "pa":  _si(pa),
        }

    mlb_pitching: dict[str, dict] = {}
    for row in fetch_current_stats_pitchers(SEASON):
        ip = float(row.get("IP") or 0)
        if ip < 0.1:
            continue
        key = normalize_name(row.get("player_name", ""))
        if not key:
            continue
        sv = float(row.get("SV") or 0)
        hld = float(row.get("HLD") or 0)
        mlb_pitching[key] = {
            "qs":   _si(row.get("QS")),
            "k":    _si(row.get("SO") or row.get("K")),  # FG uses SO
            "era":  _sf(row.get("ERA"), 2),
            "svh":  _si(sv + hld),
            "whip": _sf(row.get("WHIP"), 3),
            "ip":   _sf(ip, 1),
        }

    # MiLB stats — read milb_stats.json (built hourly by fetch_milb_stats.py)
    # No QS in MiLB; pitching uses so/era/sv+hld/whip/ip
    milb_batting: dict[str, dict] = {}
    milb_pitching: dict[str, dict] = {}
    if MILB_STATS_PATH.exists():
        milb_data = json.loads(MILB_STATS_PATH.read_text(encoding="utf-8"))
        for key, rec in milb_data.get("players", {}).items():
            s = rec.get("season") or {}
            if not s:
                continue
            if rec.get("group") == "hitting":
                pa = float(s.get("pa") or 0)
                if pa >= 1:
                    milb_batting[key] = {
                        "hr":  _si(s.get("hr")),
                        "r":   _si(s.get("r")),
                        "rbi": _si(s.get("rbi")),
                        "sb":  _si(s.get("sb")),
                        "ops": _sf(s.get("ops"), 3),
                        "pa":  _si(pa),
                    }
            elif rec.get("group") == "pitching":
                ip = float(s.get("ip") or 0)
                if ip >= 0.1:
                    sv = float(s.get("sv") or 0)
                    hld = float(s.get("hld") or 0)
                    milb_pitching[key] = {
                        "k":    _si(s.get("so")),
                        "era":  _sf(s.get("era"), 2),
                        "svh":  _si(sv + hld),
                        "whip": _sf(s.get("whip"), 3),
                        "ip":   _sf(ip, 1),
                    }
    else:
        print(f"Warning: {MILB_STATS_PATH} not found — MiLB columns will be empty")

    import datetime
    out = {
        "generated":     str(datetime.date.today()),
        "season":        SEASON,
        "mlb_batting":   mlb_batting,
        "mlb_pitching":  mlb_pitching,
        "milb_batting":  milb_batting,
        "milb_pitching": milb_pitching,
    }
    path = SITE_DATA / "season_stats.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(mlb_batting)} MLB batters, {len(mlb_pitching)} MLB pitchers, "
        f"{len(milb_batting)} MiLB batters, {len(milb_pitching)} MiLB pitchers → {path}"
    )


if __name__ == "__main__":
    build()
