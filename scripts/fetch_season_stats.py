"""
fetch_season_stats.py — MLB season stats from MLB Stats API + MiLB stats from milb_stats.json.

Uses statsapi.mlb.com/api/v1/stats (sportId=1). QS is not in the bulk season stats endpoint,
so it is computed from individual game boxscores (one per completed game, run concurrently).

Writes powerrankings/data/season_stats.json with four dicts:
  mlb_batting, mlb_pitching, milb_batting, milb_pitching

Run from the fantrax venv:
  source /Users/stevemandella/Documents/Making/fantrax/.venv/bin/activate
  python powerrankings/scripts/fetch_season_stats.py
"""
from __future__ import annotations

import datetime
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, "/Users/stevemandella/Documents/Making/fantrax")
from src.shared.utils import normalize_name

SEASON = datetime.date.today().year
BOT_ROOT = Path(__file__).resolve().parent.parent.parent
MILB_STATS_PATH = BOT_ROOT / "data" / "milb_stats.json"
SITE_DATA = Path(__file__).resolve().parent.parent / "data"

_STATS_URL = "https://statsapi.mlb.com/api/v1/stats"
_HEADERS = {"User-Agent": "fantrax-dynasty-bot/season-stats"}
_QS_WORKERS = 20


def _ip_to_float(s) -> float:
    """Convert baseball innings notation '45.2' (2 outs) to float 45.667."""
    try:
        f = float(str(s or 0))
        whole = int(f)
        outs = round((f - whole) * 10)
        return whole + outs / 3.0
    except (ValueError, TypeError):
        return 0.0


def _si(v):
    try:
        return int(round(float(v))) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _sf(v, d):
    try:
        return round(float(v), d) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _fetch_mlb(group: str) -> list[dict]:
    params = {
        "stats": "season",
        "group": group,
        "season": SEASON,
        "sportId": 1,
        "limit": 2000,
        "playerPool": "ALL_CURRENT",
    }
    resp = requests.get(_STATS_URL, params=params, headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    print(f"MLB API {group}: {len(splits)} rows")
    return splits


def _fetch_completed_game_pks(season: int) -> list[int]:
    """Return gamePks for all completed regular-season games."""
    resp = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={
            "sportId": 1,
            "season": season,
            "gameType": "R",
            "startDate": f"{season}-01-01",
            "endDate": datetime.date.today().isoformat(),
        },
        headers=_HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    return [
        g["gamePk"]
        for date_entry in resp.json().get("dates", [])
        for g in date_entry.get("games", [])
        if g.get("status", {}).get("abstractGameState") == "Final"
    ]


def _boxscore_qs(game_pk: int) -> list[tuple[str, bool]]:
    """Return (normalize_name, is_qs) pairs for each starting pitcher in this game."""
    try:
        resp = requests.get(
            f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore",
            headers=_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        bs = resp.json()
    except Exception:
        return []

    results = []
    for side in ("home", "away"):
        team = bs.get("teams", {}).get(side, {})
        players = team.get("players", {})
        for pid in team.get("pitchers", []):
            pdata = players.get(f"ID{pid}", {})
            ps = pdata.get("stats", {}).get("pitching", {})
            if not ps.get("gamesStarted"):
                continue
            name = pdata.get("person", {}).get("fullName", "")
            if not name:
                continue
            ip = _ip_to_float(ps.get("inningsPitched", "0"))
            er = int(ps.get("earnedRuns") or 0)
            results.append((normalize_name(name), ip >= 6.0 and er <= 3))
    return results


def _compute_qs(season: int) -> dict[str, int]:
    """Concurrently fetch boxscores and tally QS per pitcher."""
    game_pks = _fetch_completed_game_pks(season)
    print(f"Computing QS from {len(game_pks)} completed games ({_QS_WORKERS} workers)...")
    qs: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=_QS_WORKERS) as pool:
        futures = {pool.submit(_boxscore_qs, pk): pk for pk in game_pks}
        for i, future in enumerate(as_completed(futures), 1):
            for key, is_qs in future.result():
                if is_qs:
                    qs[key] = qs.get(key, 0) + 1
            if i % 100 == 0:
                print(f"  {i}/{len(game_pks)} boxscores processed")
    print(f"QS computed: {len(qs)} pitchers with ≥1 QS")
    return qs


def build() -> None:
    # MLB hitting
    mlb_batting: dict[str, dict] = {}
    for sp in _fetch_mlb("hitting"):
        name = (sp.get("player") or {}).get("fullName") or ""
        if not name:
            continue
        s = sp.get("stat") or {}
        pa = int(s.get("plateAppearances") or 0)
        if pa < 1:
            continue
        mlb_batting[normalize_name(name)] = {
            "hr":  _si(s.get("homeRuns")),
            "r":   _si(s.get("runs")),
            "rbi": _si(s.get("rbi")),
            "sb":  _si(s.get("stolenBases")),
            "ops": _sf(s.get("ops"), 3),
            "pa":  pa,
        }

    # MLB pitching (QS filled in below)
    mlb_pitching: dict[str, dict] = {}
    gs_by_key: dict[str, int] = {}  # track gamesStarted to distinguish starters from relievers
    for sp in _fetch_mlb("pitching"):
        name = (sp.get("player") or {}).get("fullName") or ""
        if not name:
            continue
        s = sp.get("stat") or {}
        ip = _ip_to_float(s.get("inningsPitched"))
        if ip < 0.1:
            continue
        key = normalize_name(name)
        sv  = int(s.get("saves") or 0)
        hld = int(s.get("holds") or 0)
        gs  = int(s.get("gamesStarted") or 0)
        gs_by_key[key] = gs
        mlb_pitching[key] = {
            "qs":   None,  # filled after QS computation
            "k":    _si(s.get("strikeOuts")),
            "era":  _sf(s.get("era"), 2),
            "svh":  sv + hld,
            "whip": _sf(s.get("whip"), 3),
            "ip":   round(ip, 1),
        }

    # Compute QS from boxscores
    qs_counts = _compute_qs(SEASON)
    for key, rec in mlb_pitching.items():
        if gs_by_key.get(key, 0) > 0:
            # Has at least one start — show actual QS count (may be 0)
            rec["qs"] = qs_counts.get(key, 0)
        # Pure relievers (gs=0) stay None → renders as — on site

    # MiLB stats from milb_stats.json
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
                    sv  = float(s.get("sv") or 0)
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

    out = {
        "generated":    str(datetime.date.today()),
        "season":       SEASON,
        "mlb_batting":  mlb_batting,
        "mlb_pitching": mlb_pitching,
        "milb_batting": milb_batting,
        "milb_pitching": milb_pitching,
    }
    path = SITE_DATA / "season_stats.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(mlb_batting)} MLB batters, {len(mlb_pitching)} MLB pitchers "
        f"({sum(1 for r in mlb_pitching.values() if r['qs'] is not None)} with QS data), "
        f"{len(milb_batting)} MiLB batters, {len(milb_pitching)} MiLB pitchers → {path}"
    )


if __name__ == "__main__":
    build()
