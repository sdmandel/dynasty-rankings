#!/usr/bin/env python3
"""
prepare_rankings.py — Generate weekly dynasty power rankings prompt data.

Gathers standings from standings.db (roto), HKB league power rankings, recent
trades, and roster breakdowns from the dynasty rankings CSV, then formats a
ready-to-paste prompt block for Claude.

Usage:
    python -m powerrankings.prepare_rankings --week 1
    python -m powerrankings.prepare_rankings --week 1 --csv path/to/rankings.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# Allow running as a module from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.shared.patch  # noqa: F401
from src.shared.auth import get_requests_session
from src.shared.config import DATA_DIR, FANTRAX_LEAGUE_ID, HKB_LEAGUE_URL
from src.shared.constants import USER_AGENT

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
RANKINGS_CSV = Path(DATA_DIR) / "rankings_latest.csv"


# ── Fantrax standings (roto from standings.db) ───────────────────────────────


def fetch_standings_from_db() -> list[dict]:
    """Read the latest roto standings snapshot from standings.db."""
    db_path = Path(DATA_DIR) / "standings.db"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        # Get the two most recent distinct snapshot dates
        dates = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT snapshot_date FROM standings ORDER BY snapshot_date DESC LIMIT 2"
            )
        ]
        if not dates:
            return []

        latest = dates[0]
        prev = dates[1] if len(dates) > 1 else None

        # Build rank lookup for previous date
        prev_ranks: dict[str, int] = {}
        if prev:
            for row in conn.execute(
                "SELECT team_name, rank FROM standings WHERE snapshot_date=?", (prev,)
            ):
                prev_ranks[row[0]] = row[1]

        rows = []
        for row in conn.execute(
            """SELECT rank, team_name, roto_pts,
                      cat_r, cat_hr, cat_rbi, cat_sb, cat_ops,
                      cat_qs, cat_k, cat_era, cat_whip, cat_svh
               FROM standings WHERE snapshot_date=? ORDER BY rank""",
            (latest,),
        ):
            rank, team, pts, R, HR, RBI, SB, OPS, QS, K, ERA, WHIP, SVH = row
            prev_rank = prev_ranks.get(team)
            rows.append(
                {
                    "rank": rank,
                    "team_name": team,
                    "roto_pts": pts,
                    "prev_rank": prev_rank,
                    "cat_r": R,
                    "cat_hr": HR,
                    "cat_rbi": RBI,
                    "cat_sb": SB,
                    "cat_ops": OPS,
                    "cat_qs": QS,
                    "cat_k": K,
                    "cat_era": ERA,
                    "cat_whip": WHIP,
                    "cat_svh": SVH,
                    "snapshot_date": latest,
                }
            )
        return rows
    finally:
        conn.close()


def _ordinal(n: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
    return f"{n}{suffix}"


def parse_last_standings(value: str) -> dict[str, int]:
    """Parse --last-standings value: JSON file path or comma-separated team names."""
    import json

    path = Path(value)
    if path.exists():
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return {name: i + 1 for i, name in enumerate(data)}
        elif isinstance(data, dict):
            result = {}
            for name, val in data.items():
                result[name] = int(val["rank"] if isinstance(val, dict) else val)
            return result
        return {}
    # Comma-separated list of team names in order
    names = [n.strip() for n in value.split(",") if n.strip()]
    return {name: i + 1 for i, name in enumerate(names)}


def format_standings(rows: list[dict], last_standings: dict[str, int] | None = None) -> str:
    """Format roto standings into a text table.

    Rank deltas are taken from last_standings if provided, otherwise from the
    prev_rank field already embedded in each row by fetch_standings_from_db.
    """
    if not rows:
        return "(Standings not yet available — preseason)"

    date_label = rows[0].get("snapshot_date", "")

    lines = [
        f"As of {date_label}",
        f"{'Rank':<5} {'Team':<28} {'Pts':<7} {'Chg (rank)':<18} {'R':<5} {'HR':<5} {'RBI':<5} {'SB':<5} {'OPS':<5} {'QS':<5} {'K':<5} {'ERA':<5} {'WHIP':<5} {'SVH':<5}",
        "-" * 125,
    ]
    for r in rows:
        if last_standings:
            prev_rank = last_standings.get(r["team_name"])
        else:
            prev_rank = r.get("prev_rank")

        if prev_rank and prev_rank != r["rank"]:
            delta = prev_rank - r["rank"]
            sign = "+" if delta > 0 else ""
            chg = f"{sign}{delta} (was {_ordinal(prev_rank)})"
        elif prev_rank:
            chg = "— (no change)"
        else:
            chg = "— (N/A)"

        lines.append(
            f"#{r['rank']:<4} {r['team_name']:<28} {r['roto_pts']:<7.1f} {chg:<18}"
            f" {r['cat_r']:<5} {r['cat_hr']:<5} {r['cat_rbi']:<5} {r['cat_sb']:<5}"
            f" {r['cat_ops']:<5} {r['cat_qs']:<5} {r['cat_k']:<5}"
            f" {r['cat_era']:<5} {r['cat_whip']:<5} {r['cat_svh']:<5}"
        )
    lines.append("")

    return "\n".join(lines)


# ── Lineup activity ──────────────────────────────────────────────────────────


def _completed_week_range() -> tuple[date, date]:
    """Return (sunday, saturday) for the most recently completed Sun–Sat fantasy week.

    Always returns the completed week regardless of what day this is run,
    so Monday re-runs don't bleed prior-week activity into the new week count.
    """
    from datetime import timedelta

    today = date.today()
    # weekday(): Mon=0 … Sat=5, Sun=6
    # Days elapsed since last Saturday (0 if today IS Saturday, 1 if Sunday, 2 if Monday, …)
    days_since_sat = (today.weekday() - 5) % 7
    last_saturday = today - timedelta(days=days_since_sat)
    last_sunday = last_saturday - timedelta(days=6)
    return last_sunday, last_saturday


def fetch_lineup_activity(session, week_start: date, week_end: date) -> dict[str, int]:
    """Return {team_name: session_count} for lineup changes within the given Sun–Sat week."""
    league_id = FANTRAX_LEAGUE_ID
    url = f"https://www.fantrax.com/fxpa/req?leagueId={league_id}"
    start_dt = datetime(week_start.year, week_start.month, week_start.day)
    end_dt   = datetime(week_end.year,  week_end.month,  week_end.day, 23, 59, 59)

    all_rows: list[dict] = []
    for page in range(1, 5):  # cap at 4 pages (800 rows) to avoid runaway
        payload = {
            "msgs": [
                {
                    "method": "getTransactionDetailsHistory",
                    "data": {
                        "maxResultsPerPage": "200",
                        "statusOrDate": "PROCESSED",
                        "view": "LINEUP_CHANGE",
                        "pageNumber": str(page),
                    },
                }
            ]
        }
        try:
            resp = session.post(url, json=payload, timeout=15)
            data = resp.json().get("responses", [{}])[0].get("data", {})
            rows = data.get("table", {}).get("rows", [])
            all_rows.extend(rows)
            total_pages = data.get("paginatedResultSet", {}).get("totalNumPages", 1)
            if page >= total_pages:
                break
        except Exception as e:
            log.warning("Could not fetch lineup changes (page %d): %s", page, e)
            break

    # Count distinct txSetIds per team within the week window
    sessions: dict[str, set[str]] = defaultdict(set)
    for row in all_rows:
        tx_id = row.get("txSetId", "")
        team = date_str = ""
        for cell in row.get("cells", []):
            k, c = cell.get("key", ""), cell.get("content", "")
            if k == "team":
                team = c
            elif k == "date":
                date_str = c
        if not team or not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%a %b %d, %Y, %I:%M%p")
        except ValueError:
            continue
        if start_dt <= dt <= end_dt:
            sessions[team].add(tx_id)

    return {team: len(s) for team, s in sessions.items()}


def format_lineup_activity(
    activity: dict[str, int],
    week_start: date,
    week_end: date,
    known_teams: set[str] | None = None,
) -> str:
    """Format lineup activity as a sorted table, highlighting inactive teams.

    known_teams: full league team list — teams absent from the API response
    are assumed to have 0 sessions and are shown with a ⚠ flag.
    """
    # Fill in zeros for any known team that had no changes (absent from API)
    if known_teams:
        for team in known_teams:
            if team not in activity:
                activity[team] = 0

    if not activity:
        return "(No lineup change data available)"

    week_label = f"{week_start.strftime('%b %d')}–{week_end.strftime('%b %d')}"
    lines = [f"Lineup change sessions per team (week of {week_label}):"]
    lines.append(f"  {'Team':<28} {'Sessions':>8}  {'Activity'}")
    lines.append("  " + "-" * 55)

    for team, count in sorted(activity.items(), key=lambda x: x[1]):
        if count == 0:
            flag = "⚠ NOT SETTING LINEUP"
        elif count <= 2:
            flag = "low"
        elif count <= 5:
            flag = "moderate"
        else:
            flag = "active"
        lines.append(f"  {team:<28} {count:>8}  {flag}")

    return "\n".join(lines)


# ── Recent trades ────────────────────────────────────────────────────────────


def fetch_trades(session, week_start: date | None = None, week_end: date | None = None) -> list[dict]:
    """Fetch executed trades from the Fantrax API.

    If week_start/week_end are provided, only returns trades within that window.
    """
    league_id = FANTRAX_LEAGUE_ID
    url = f"https://www.fantrax.com/fxpa/req?leagueId={league_id}"
    payload = {
        "msgs": [
            {
                "method": "getTransactionDetailsHistory",
                "data": {
                    "maxResultsPerPage": "200",
                    "statusOrDate": "PROCESSED",
                    "view": "TRADE",
                },
            }
        ]
    }
    try:
        resp = session.post(url, json=payload, timeout=15)
        rows = resp.json().get("responses", [{}])[0].get("data", {}).get("table", {}).get("rows", [])
    except Exception as e:
        log.warning("Could not fetch trades: %s", e)
        return []

    # Group rows by txSetId
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        groups[row["txSetId"]].append(row)

    trades = []
    for tx_id, tx_rows in groups.items():
        date_str = period = ""
        moves = []  # (player_label, from_team, to_team)

        for row in tx_rows:
            scorer = row.get("scorer", {})
            dp = row.get("draftPickDisplayParts", {})
            if scorer.get("name"):
                player = scorer["name"]
                pos = scorer.get("posShortNames", "?")
                mlb_team = scorer.get("teamShortName", "")
                icons = [ic.get("tooltip", "") for ic in scorer.get("icons", [])]
                flags = []
                if any("IL" in ic or "Injured" in ic for ic in icons):
                    flags.append("IL")
                if any("Minor" in ic or "minor" in ic for ic in icons):
                    flags.append("MiLB")
                label = f"{player} ({pos}/{mlb_team})"
                if flags:
                    label += f" [{','.join(flags)}]"
            elif dp:
                round_info = dp.get("roundInfo", "").replace("<b>", "").replace("</b>", "")
                year = dp.get("year", "").replace("<b>", "").replace("</b>", "")
                label = f"{year} {round_info}"
            else:
                label = "?"

            from_t = to_t = ""
            for cell in row.get("cells", []):
                k = cell.get("key", "")
                c = cell.get("content", "")
                if k == "from":
                    from_t = c
                elif k == "to":
                    to_t = c
                elif k == "date" and not date_str:
                    date_str = c
                elif k == "week" and not period:
                    period = c

            moves.append((label, from_t, to_t))

        # Apply date window filter if requested
        if (week_start or week_end) and date_str:
            try:
                trade_dt = datetime.strptime(date_str, "%a %b %d, %Y, %I:%M%p").date()
                if week_start and trade_dt < week_start:
                    continue
                if week_end and trade_dt > week_end:
                    continue
            except ValueError:
                pass  # unparseable date → include it

        # Summarize as two-sided trade
        receiving: dict[str, list[str]] = defaultdict(list)
        for label, from_t, to_t in moves:
            if to_t:
                receiving[to_t].append(label)

        trades.append(
            {
                "tx_id": tx_id,
                "date": date_str,
                "period": period,
                "receiving": dict(receiving),
            }
        )

    return trades


def format_trades(trades: list[dict]) -> str:
    """Format trades into readable text."""
    if not trades:
        return "(No trades found)"

    lines = []
    for t in trades:
        lines.append(f"Period {t['period']} | {t['date']}")
        for team, players in t["receiving"].items():
            lines.append(f"  {team} GETS: {' + '.join(players)}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ── HKB league power rankings ───────────────────────────────────────────────


async def _fetch_hkb_league_data() -> dict | None:
    """Intercept the /hkb/fantraxLeague JSON from the HKB rankings page."""
    from playwright.async_api import async_playwright

    result: dict | None = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT)

        async def on_response(response):
            nonlocal result
            if result is not None:
                return
            if response.status == 200 and "fantraxLeague" in response.url:
                try:
                    result = await response.json()
                except Exception as e:
                    log.warning("Failed to parse HKB response: %s", e)

        page.on("response", on_response)

        log.info("Loading HKB league page: %s", HKB_LEAGUE_URL)
        try:
            await page.goto(HKB_LEAGUE_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:
            log.debug("Page load warning (non-fatal): %s", e)

        await page.wait_for_timeout(6_000)
        await browser.close()

    return result


def fetch_hkb_power_rankings() -> list[dict]:
    """Get HKB team power rankings sorted by total roster value."""
    data = asyncio.run(_fetch_hkb_league_data())
    if not data:
        return []

    teams = []
    for team in data.get("teams", []):
        team_name = team.get("teamName") or ""
        players = team.get("players", [])
        total_value = sum(p.get("value", 0) or 0 for p in players)
        player_count = len(players)
        top_player = min(players, key=lambda p: p.get("rank", 9999)) if players else {}
        teams.append(
            {
                "team_name": team_name,
                "total_value": total_value,
                "player_count": player_count,
                "top_player": top_player.get("name", ""),
                "top_rank": top_player.get("rank", 0),
            }
        )

    teams.sort(key=lambda t: t["total_value"], reverse=True)
    for i, t in enumerate(teams, 1):
        t["hkb_power_rank"] = i
    return teams


def format_hkb_rankings(teams: list[dict]) -> str:
    """Format HKB power rankings into text."""
    if not teams:
        return "(HKB data not available)"
    lines = [
        f"{'#':>3}  {'Team':<35}  {'Value':>8}  {'Players':>7}  {'Top Player':<25}"
    ]
    lines.append("-" * 85)
    for t in teams:
        lines.append(
            f"  {t['hkb_power_rank']:>2}  {t['team_name']:<35}  {t['total_value']:>8,}  "
            f"{t['player_count']:>7}  #{t['top_rank']} {t['top_player']:<20}"
        )
    return "\n".join(lines)


# ── Algo team rankings (from dynasty rankings CSV) ───────────────────────────


def compute_algo_team_rankings(csv_rows: list[dict]) -> list[dict]:
    """Sum composite Score per team from the dynasty rankings CSV.

    Returns a list of dicts sorted by total score descending, with:
      team_name, total_score, player_count, top_player, top_rank
    """
    teams: dict[str, list[dict]] = defaultdict(list)
    for row in csv_rows:
        owner = row.get("Owned By", "").strip()
        if not owner:
            continue
        teams[owner].append(row)

    result = []
    for team_name, players in teams.items():
        scores = []
        for p in players:
            try:
                scores.append(float(p.get("Score", 0) or 0))
            except (ValueError, TypeError):
                pass
        total_score = sum(scores)

        # Top player by Overall Rank (lowest number = best)
        ranked = [p for p in players if _safe_int(p.get("Overall Rank"))]
        ranked.sort(key=lambda p: _safe_int(p.get("Overall Rank")) or 9999)
        top = ranked[0] if ranked else {}

        result.append({
            "team_name": team_name,
            "total_score": total_score,
            "player_count": len(players),
            "top_player": top.get("Player", ""),
            "top_rank": _safe_int(top.get("Overall Rank")) or 0,
        })

    result.sort(key=lambda t: t["total_score"], reverse=True)
    for i, t in enumerate(result, 1):
        t["algo_power_rank"] = i
    return result


def format_algo_rankings(teams: list[dict]) -> str:
    """Format algo composite team rankings into text."""
    if not teams:
        return "(Algo ranking data not available)"
    lines = [
        f"{'#':>3}  {'Team':<35}  {'Score':>8}  {'Players':>7}  {'Top Player':<25}"
    ]
    lines.append("-" * 85)
    for t in teams:
        lines.append(
            f"  {t['algo_power_rank']:>2}  {t['team_name']:<35}  {t['total_score']:>8.1f}  "
            f"{t['player_count']:>7}  #{t['top_rank']} {t['top_player']:<20}"
        )
    return "\n".join(lines)


# ── CSV roster breakdown ─────────────────────────────────────────────────────


def load_rankings_csv(csv_path: Path) -> list[dict]:
    """Load the dynasty rankings CSV."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_pitcher(row: dict) -> bool:
    """Check if player is a pitcher based on positions and available stats.

    Two-way players (like Ohtani) who have batting projections show as batters.
    """
    positions = row.get("Positions", "")
    player_pos = {p.strip() for p in positions.split(",")}
    bat_positions = {"C", "1B", "2B", "3B", "SS", "OF", "DH", "MI", "CI", "UT"}
    has_bat_pos = bool(player_pos & bat_positions)
    has_bat_stats = bool(row.get("St HR") or row.get("St OPS"))
    # Two-way: if they have bat positions or bat stats, show batting line
    if has_bat_pos or (has_bat_stats and row.get("St ERA")):
        return False
    has_pitch = "P" in player_pos or "SP" in player_pos or "RP" in player_pos
    return has_pitch


def format_player_stats(row: dict) -> str:
    """Format projected stats for a player."""
    if is_pitcher(row):
        parts = []
        for col, label in [
            ("St ERA", "ERA"),
            ("St K", "K"),
            ("St QS", "QS"),
            ("St SVH", "SVH"),
            ("St WHIP", "WHIP"),
        ]:
            val = row.get(col, "")
            if val:
                parts.append(f"{label} {val}")
        return " / ".join(parts) if parts else "—"
    else:
        parts = []
        for col, label in [
            ("St HR", "HR"),
            ("St R", "R"),
            ("St RBI", "RBI"),
            ("St SB", "SB"),
            ("St OPS", "OPS"),
        ]:
            val = row.get(col, "")
            if val:
                parts.append(f"{label} {val}")
        return " / ".join(parts) if parts else "—"


def build_team_breakdowns(
    rows: list[dict],
    transactions: dict[str, list[str]] | None = None,
) -> str:
    """Build per-team roster breakdowns sorted by composite score."""
    teams: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        owner = row.get("Owned By", "").strip()
        if owner:
            teams[owner].append(row)

    # Sort teams by sum of top player scores (descending)
    def team_sort_key(item):
        _name, players = item
        scores = []
        for p in players:
            try:
                scores.append(float(p.get("Score", 0)))
            except (ValueError, TypeError):
                pass
        return sum(sorted(scores, reverse=True)[:10])

    sorted_teams = sorted(teams.items(), key=team_sort_key, reverse=True)

    # Compute algo rank for each team (1 = best total score)
    team_ranks = {name: rank for rank, (name, _) in enumerate(sorted_teams, 1)}

    blocks = []
    for team_name, players in sorted_teams:
        # Sort players by score descending
        def safe_score(p):
            try:
                return float(p.get("Score", 0))
            except (ValueError, TypeError):
                return 0.0

        players.sort(key=safe_score, reverse=True)

        # Avg age
        ages = []
        for p in players:
            try:
                ages.append(float(p.get("Age", 0)))
            except (ValueError, TypeError):
                pass
        avg_age = sum(ages) / len(ages) if ages else 0

        # Prospect count
        prospect_count = sum(
            1
            for p in players
            if p.get("Level", "").strip() and p.get("Level", "").strip() != "MLB"
        )

        # Header
        algo_rank = team_ranks[team_name]
        block = [
            f"{team_name} | Algo rank: {algo_rank} | Avg age: {avg_age:.1f} | Prospects: {prospect_count}"
        ]

        # Oracle rank movers (risers = positive Δ Rank, fallers = negative)
        risers = sorted(
            [p for p in players if (_safe_int(p.get("Δ Rank")) or 0) > 0],
            key=lambda p: _safe_int(p.get("Δ Rank")) or 0,
            reverse=True,
        )[:3]
        fallers = sorted(
            [p for p in players if (_safe_int(p.get("Δ Rank")) or 0) < 0],
            key=lambda p: _safe_int(p.get("Δ Rank")) or 0,
        )[:3]
        new_players = [p for p in players if not p.get("Prior Rank", "").strip()][:3]

        block.append("Oracle rank movers this week:")
        if risers or new_players:
            block.append("  ↑ Risers:")
            for p in risers:
                prior = p.get("Prior Rank", "?")
                curr = p.get("Overall Rank", "?")
                delta = _safe_int(p.get("Δ Rank")) or 0
                block.append(f"    {p.get('Player', '?')}: #{prior} → #{curr} (+{delta})")
            for p in new_players:
                curr = p.get("Overall Rank", "?")
                block.append(f"    {p.get('Player', '?')}: NEW → #{curr}")
        else:
            block.append("  ↑ Risers: none")

        if fallers:
            block.append("  ↓ Fallers:")
            for p in fallers:
                prior = p.get("Prior Rank", "?")
                curr = p.get("Overall Rank", "?")
                delta = _safe_int(p.get("Δ Rank")) or 0
                block.append(f"    {p.get('Player', '?')}: #{prior} → #{curr} ({delta})")
        else:
            block.append("  ↓ Fallers: none")

        # Transactions
        team_txns = (transactions or {}).get(team_name, [])
        if team_txns:
            block.append("Transactions this period:")
            for txn in team_txns:
                block.append(f"  - {txn}")
        else:
            block.append("Transactions: none")

        # Flags
        flags = []
        low_ranked = [
            p
            for p in players
            if _safe_int(p.get("Overall Rank")) and _safe_int(p.get("Overall Rank")) >= 700
        ]
        if low_ranked:
            names = ", ".join(f"{p['Player']} (#{p['Overall Rank']})" for p in low_ranked)
            flags.append(f"Ranked 700+: {names}")

        old_players = [
            p
            for p in players
            if _safe_float(p.get("Age")) and _safe_float(p.get("Age")) >= 33
        ]
        if old_players:
            names = ", ".join(f"{p['Player']} (age {p['Age']})" for p in old_players)
            flags.append(f"Age 33+: {names}")

        if flags:
            block.append("Flags: " + " | ".join(flags))
        else:
            block.append("Flags: none")

        blocks.append("\n".join(block))

    return "\n\n".join(blocks)


def _safe_int(val) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── Output ───────────────────────────────────────────────────────────────────


def build_prompt(
    week: int,
    standings_text: str,
    algo_rankings_text: str,
    lineup_activity_text: str,
    roster_text: str,
) -> str:
    today = date.today().strftime("%B %d, %Y")
    return f"""---
WEEK {week} DYNASTY POWER RANKINGS — DATA DUMP
{today}

CURRENT STANDINGS (roto points, 5x5):
{standings_text}

ALGO COMPOSITE TEAM RANKINGS (sum of dynasty composite scores per roster):
{algo_rankings_text}

LINEUP MANAGEMENT ACTIVITY:
{lineup_activity_text}

ROSTER BREAKDOWN BY TEAM:
(sorted by composite score descending; includes Oracle rank movers and transactions per team)

{roster_text}

---
PASTE EVERYTHING ABOVE INTO CLAUDE WEB UI WITH THIS INSTRUCTION:

Using the replication guide in this project, generate Week {week} power
rankings. This is Week 2+: do not re-introduce rosters. Cover what
happened this week — standings movement, Oracle rank movers, transactions,
and trajectory.

Add your manual context below before pasting:
[TRADES / INJURIES / CALL-UPS / NOTABLE MOMENTS NOT CAPTURED ABOVE]

Generate the full HTML file using the exact template from the replication guide.
---"""


def copy_to_clipboard(text: str) -> bool:
    """Copy text to macOS clipboard. Returns True on success."""
    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False



# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    import json

    parser = argparse.ArgumentParser(
        description="Generate weekly dynasty power rankings prompt"
    )
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--no-standings", action="store_true", help="Skip standings fetch"
    )
    parser.add_argument(
        "--last-standings",
        type=str,
        default=None,
        help=(
            "Last week's standings for rank-change delta. "
            "JSON file path OR comma-separated team names in order (1st to last)."
        ),
    )
    parser.add_argument(
        "--transactions",
        type=str,
        default=None,
        help='JSON file: {"Team Name": ["note1", "note2"], ...}',
    )
    parser.add_argument(
        "--no-lineup-activity",
        action="store_true",
        help="Skip lineup change activity fetch",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Resolve CSV — always use the canonical output from dynasty_rankings.py
    csv_path = RANKINGS_CSV
    if not csv_path.exists():
        print(f"ERROR: rankings CSV not found: {csv_path}")
        print("Run 'python -m src.rankings.dynasty_rankings' first to generate it.")
        sys.exit(1)
    log.info("Using CSV: %s", csv_path)

    # Last-standings delta
    last_standings: dict[str, int] | None = None
    if args.last_standings:
        try:
            last_standings = parse_last_standings(args.last_standings)
            log.info("Loaded last standings for %d teams", len(last_standings))
        except Exception as e:
            log.warning("Could not parse --last-standings: %s", e)

    # Standings (from standings.db)
    known_teams: set[str] = set()
    if args.no_standings:
        standings_text = "(Skipped)"
    else:
        log.info("Reading standings from standings.db…")
        try:
            standing_rows = fetch_standings_from_db()
            standings_text = format_standings(standing_rows, last_standings)
            known_teams.update(r["team_name"] for r in standing_rows)
        except Exception as e:
            log.warning("Could not read standings: %s", e)
            standings_text = f"(Error reading standings: {e})"

    # Algo composite team rankings (computed from dynasty CSV)
    # Load CSV rows now so we can reuse them for roster breakdowns below
    csv_rows = load_rankings_csv(csv_path)
    log.info("Computing algo composite team rankings from CSV…")
    try:
        algo_teams = compute_algo_team_rankings(csv_rows)
        algo_rankings_text = format_algo_rankings(algo_teams)
        known_teams.update(t["team_name"] for t in algo_teams)
    except Exception as e:
        log.warning("Could not compute algo rankings: %s", e)
        algo_rankings_text = f"(Error computing algo rankings: {e})"

    # Per-team transactions — auto-fetch trades within the completed week window
    week_start, week_end = _completed_week_range()
    transactions: dict[str, list[str]] = defaultdict(list)
    log.info("Fetching trades from Fantrax (window: %s–%s)…", week_start, week_end)
    try:
        trade_session = get_requests_session()
        fetched_trades = fetch_trades(trade_session, week_start=week_start, week_end=week_end)
        for trade in fetched_trades:
            period = trade.get("period", "?")
            date_str = trade.get("date", "")
            receiving = trade.get("receiving", {})
            # Build the two sides of the trade for labeling
            all_teams = list(receiving.keys())
            for team, players in receiving.items():
                other_teams = [t for t in all_teams if t != team]
                other = " & ".join(other_teams) if other_teams else "?"
                label = f"Period {period} ({date_str}): acquired {' + '.join(players)} from {other}"
                transactions[team].append(label)
        log.info("Fetched %d trade(s)", len(fetched_trades))
    except Exception as e:
        log.warning("Could not fetch trades: %s", e)

    if args.transactions:
        try:
            manual = json.loads(Path(args.transactions).read_text())
            for team, notes in manual.items():
                transactions[team].extend(notes)
            log.info("Merged manual transactions for %d teams", len(manual))
        except Exception as e:
            log.warning("Could not load --transactions file: %s", e)

    transactions = dict(transactions) if transactions else None

    # Lineup activity (reuses the same week_start/week_end window as trades)
    if args.no_lineup_activity:
        lineup_activity_text = "(Skipped)"
    else:
        log.info("Fetching lineup activity for %s–%s…", week_start, week_end)
        try:
            activity_session = get_requests_session()
            activity = fetch_lineup_activity(activity_session, week_start, week_end)
            lineup_activity_text = format_lineup_activity(
                activity, week_start, week_end, known_teams=known_teams or None
            )
        except Exception as e:
            log.warning("Could not fetch lineup activity: %s", e)
            lineup_activity_text = f"(Error fetching lineup activity: {e})"

    # Roster breakdowns (csv_rows already loaded above)
    log.info("Processing roster breakdowns…")
    roster_text = build_team_breakdowns(csv_rows, transactions)

    # Build prompt
    prompt = build_prompt(args.week, standings_text, algo_rankings_text, lineup_activity_text, roster_text)

    # Output
    print(prompt)

    output_path = SCRIPT_DIR / "weekly_prompt.txt"
    output_path.write_text(prompt, encoding="utf-8")
    log.info("Saved to %s", output_path)

    if copy_to_clipboard(prompt):
        log.info("Copied to clipboard ✓")
    else:
        log.warning("Could not copy to clipboard (pbcopy not available)")


if __name__ == "__main__":
    main()
