"""Build the public Oracle payload for the static site.

This script only emits derived/public-facing summaries. It does not publish
the private rankings CSV or player-level valuation inputs.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

SEASON = 2026

VALUE_INPUT = {
    "John Henry Fan Club": {"oracle_rank": 1, "total_value": 35777.0, "mlb_value": 24934.3, "farm_value": 10842.7, "avg_age": 27.3},
    "Rollie Fingers": {"oracle_rank": 2, "total_value": 35362.6, "mlb_value": 28024.6, "farm_value": 7338.0, "avg_age": 28.0},
    "Seam heads": {"oracle_rank": 3, "total_value": 33387.7, "mlb_value": 26732.1, "farm_value": 6655.6, "avg_age": 28.7},
    "Humongous Melonheads": {"oracle_rank": 4, "total_value": 31778.0, "mlb_value": 27481.5, "farm_value": 4296.5, "avg_age": 28.1},
    "Acuña Matata": {"oracle_rank": 5, "total_value": 31419.7, "mlb_value": 25292.6, "farm_value": 6127.1, "avg_age": 27.8},
    "Inkers": {"oracle_rank": 6, "total_value": 28426.3, "mlb_value": 20811.2, "farm_value": 7615.1, "avg_age": 28.6},
    "Vin Mazzaro fan club": {"oracle_rank": 7, "total_value": 25664.1, "mlb_value": 22356.6, "farm_value": 3307.5, "avg_age": 28.3},
    "Millville Meteors": {"oracle_rank": 8, "total_value": 24831.6, "mlb_value": 22648.3, "farm_value": 2183.3, "avg_age": 29.4},
    "Trazadone": {"oracle_rank": 9, "total_value": 22979.9, "mlb_value": 18682.0, "farm_value": 4297.9, "avg_age": 30.2},
    "Mommy": {"oracle_rank": 10, "total_value": 22107.0, "mlb_value": 21122.6, "farm_value": 984.4, "avg_age": 30.5},
    "Sam": {"oracle_rank": 11, "total_value": 21301.5, "mlb_value": 19086.7, "farm_value": 2214.8, "avg_age": 29.9},
    "Pat": {"oracle_rank": 12, "total_value": 21243.3, "mlb_value": 20316.2, "farm_value": 927.1, "avg_age": 31.2},
}

CATEGORY_CODE_TO_LABEL = {
    "cat_r": "R",
    "cat_hr": "HR",
    "cat_rbi": "RBI",
    "cat_sb": "SB",
    "cat_ops": "OPS",
    "cat_qs": "QS",
    "cat_k": "K",
    "cat_era": "ERA",
    "cat_whip": "WHIP",
    "cat_svh": "SVH",
}

def load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def load_team_registry() -> tuple[dict[str, str], dict[str, str]]:
    data = load_json("team_registry.json")
    alias_to_display: dict[str, str] = {}
    display_to_key: dict[str, str] = {}
    for row in data.get("teams", []):
        display_name = row["display_name"]
        display_to_key[display_name] = row["team_key"]
        for alias in row.get("aliases", []):
            alias_to_display[alias] = display_name
    return alias_to_display, display_to_key


def derive_public_archetypes(team: dict, manager: dict | None, standings_row: dict, median_total: float) -> list[str]:
    farm_share = team["farm_share"]
    avg_age = team["avg_age"]
    tier = team["contention_tier"]
    categories = standings_row.get("categories", {})
    svh_pts = float(categories.get("SVH", {}).get("pts", 0))
    sb_pts = float(categories.get("SB", {}).get("pts", 0))
    ops_pts = float(categories.get("OPS", {}).get("pts", 0))
    qs_pts = float(categories.get("QS", {}).get("pts", 0))
    era_pts = float(categories.get("ERA", {}).get("pts", 0))

    archetypes: list[str] = [tier]

    if tier in {"fringe", "stagnating"} and farm_share >= 0.19 and avg_age <= 29.2:
        archetypes.append("soft retool")
    if farm_share >= 0.22:
        archetypes.append("asset hoarder")

    category_values = [float(info.get("pts", 0)) for info in categories.values()]
    if category_values:
        spread = max(category_values) - min(category_values)
        if spread >= 5 or max(svh_pts, sb_pts, ops_pts) >= 10.5:
            archetypes.append("category specialist")

    if svh_pts >= 9.5 and (team["pressure"]["loss_risk"]["category"] == "SVH" or team["pressure"]["gain_target"]["category"] == "SVH"):
        archetypes.append("bullpen-dependent")

    if avg_age >= 29.8 and team["farm_share"] <= 0.15 and team["total_value"] >= median_total * 0.78:
        archetypes.append("aging core")

    if manager and manager.get("archetype") == "trader" and "soft retool" not in archetypes and tier == "fringe":
        archetypes.append("soft retool")
    if manager and manager.get("archetype") == "grinder" and qs_pts + era_pts >= 15 and "category specialist" not in archetypes:
        archetypes.append("category specialist")

    deduped: list[str] = []
    for item in archetypes:
        if item not in deduped:
            deduped.append(item)
    return deduped[:3]


def derive_pressure(category_gaps: dict) -> dict:
    gain_rows: list[tuple[str, float]] = []
    loss_rows: list[tuple[str, float]] = []
    for cat_code, gap_info in category_gaps.items():
        to_gain = gap_info.get("to_gain")
        to_loss = gap_info.get("to_loss")
        if to_gain is not None:
            gain_rows.append((CATEGORIES.get(cat_code, cat_code), float(to_gain)))
        if to_loss is not None:
            loss_rows.append((CATEGORIES.get(cat_code, cat_code), float(to_loss)))

    gain_rows.sort(key=lambda row: (row[1], row[0]))
    loss_rows.sort(key=lambda row: (row[1], row[0]))

    gain_target = gain_rows[0] if gain_rows else ("-", None)
    loss_risk = loss_rows[0] if loss_rows else ("-", None)
    min_gap = min(
        [row[1] for row in gain_rows[:1] + loss_rows[:1] if row[1] is not None],
        default=4.0,
    )

    pressure_score = round(max(0.0, 100 - (min_gap * 22)), 1)
    summary_parts = []
    if gain_target[0] != "-":
        summary_parts.append(f"closest gain: {gain_target[0]} ({gain_target[1]:.1f})")
    if loss_risk[0] != "-":
        summary_parts.append(f"closest loss: {loss_risk[0]} ({loss_risk[1]:.1f})")

    return {
        "score": pressure_score,
        "gain_target": {"category": gain_target[0], "gap": gain_target[1]},
        "loss_risk": {"category": loss_risk[0], "gap": loss_risk[1]},
        "summary": " · ".join(summary_parts) if summary_parts else "No tight category edges.",
    }


def derive_trade_needs(team: dict, standings_row: dict) -> list[str]:
    categories = standings_row.get("categories", {})
    pressure = team["pressure"]
    notes: list[str] = []
    gain_cat = pressure["gain_target"]["category"]
    loss_cat = pressure["loss_risk"]["category"]
    farm_share = team["farm_share"]

    if gain_cat == "SVH" or float(categories.get("SVH", {}).get("pts", 0)) <= 5.5:
        notes.append("needs saves")
    if gain_cat in {"QS", "K", "ERA", "WHIP"} or loss_cat in {"QS", "K", "ERA", "WHIP"}:
        notes.append("fragile SP depth")
    if float(categories.get("SB", {}).get("pts", 0)) >= 9.0 and (
        pressure["loss_risk"]["category"] != "SB" or (pressure["loss_risk"]["gap"] or 99) > 1.5
    ):
        notes.append("surplus SB")
    if farm_share >= 0.2:
        notes.append("can trade prospects")
    if gain_cat in {"OPS", "HR", "RBI"}:
        notes.append("needs impact bats")

    deduped: list[str] = []
    for item in notes:
        if item not in deduped:
            deduped.append(item)
    return deduped[:3] or ["hold and monitor"]


def derive_trend(team: dict, standings_row: dict) -> dict:
    del standings_row
    tier = team["contention_tier"]
    gain_cat = team["pressure"]["gain_target"]["category"]
    gain_gap = team["pressure"]["gain_target"]["gap"]
    loss_cat = team["pressure"]["loss_risk"]["category"]
    loss_gap = team["pressure"]["loss_risk"]["gap"]
    farm_share = team["farm_share"]
    avg_age = team["avg_age"]

    if tier == "contender":
        stock = "push"
        summary = f"Window open · pressure in {gain_cat}" if gain_cat != "-" else "Window open"
    elif tier == "fringe" and farm_share >= 0.18 and avg_age <= 29.2:
        stock = "retool"
        summary = "Soft retool path"
    elif tier == "rebuilding" and farm_share >= 0.2:
        stock = "build"
        summary = "Farm-forward build"
    elif avg_age >= 29.8 and farm_share <= 0.15:
        stock = "age"
        summary = "Aging core under pressure"
    elif gain_gap is not None and gain_gap <= 0.5:
        stock = "edge"
        summary = f"One move from gaining {gain_cat}"
    elif loss_gap is not None and loss_gap <= 0.5:
        stock = "risk"
        summary = f"Protecting {loss_cat}"
    else:
        stock = "hold"
        summary = "Holding current shape"

    return {
        "stock": stock,
        "summary": summary,
        "rank_delta": None,
        "tier_change": None,
        "farm_delta": None,
    }


def main() -> None:
    global CATEGORIES
    standings = load_json("standings.json")
    intelligence = load_json("league_intelligence.json")
    managers = load_json("managers.json")
    alias_to_display, _display_to_key = load_team_registry()

    standings_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in standings["teams"]}
    intel_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in intelligence["teams"]}
    manager_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in managers["managers"]}
    median_total = median(team["total_value"] for team in VALUE_INPUT.values())

    CATEGORIES = CATEGORY_CODE_TO_LABEL
    teams: list[dict] = []
    for team_name, raw in sorted(VALUE_INPUT.items(), key=lambda item: item[1]["oracle_rank"]):
        standings_row = standings_by_team[team_name]
        intel_row = intel_by_team[team_name]

        team = {
            "team": team_name,
            "oracle_rank": raw["oracle_rank"],
            "standings_rank": standings_row["rank"],
            "total_value": raw["total_value"],
            "mlb_value": raw["mlb_value"],
            "farm_value": raw["farm_value"],
            "avg_age": raw["avg_age"],
            "farm_share": round(raw["farm_value"] / raw["total_value"], 4),
            "contention_tier": intel_row["tier"],
            "points_back": intel_row["points_back"],
            "reachable_points": intel_row["reachable_points"],
            "tight_categories": [CATEGORIES.get(cat, cat) for cat in intel_row.get("tight_categories", [])],
            "category_gaps": {
                CATEGORIES.get(cat, cat): values for cat, values in intel_row.get("category_gaps", {}).items()
            },
            "luck_delta": intel_row["luck"]["delta"],
            "volatility": intel_row["volatility"]["team_volatility_score"],
        }
        team["pressure"] = derive_pressure(intel_row.get("category_gaps", {}))
        team["public_archetypes"] = derive_public_archetypes(team, manager_by_team.get(team_name), standings_row, median_total)
        team["trade_needs"] = derive_trade_needs(team, standings_row)
        team["trend"] = derive_trend(team, standings_row)
        teams.append(team)

    payload = {
        "generated": standings.get("generated"),
        "generated_at": standings.get("generated_at"),
        "season": SEASON,
        "season_label": f"{SEASON} Season",
        "week": standings.get("week"),
        "snapshot_date": intelligence.get("snapshot_date"),
        "sources": {
            "standings": standings.get("generated_at") or standings.get("generated"),
            "intelligence": intelligence.get("generated"),
            "managers": managers.get("generated"),
            "oracle_values": "weekly_oracle_export",
        },
        "notes": {
            "privacy": "Private rankings CSV remains unpublished. This payload contains only derived/public summaries.",
            "oracle_window": "Oracle value = public team-level aggregate, not player-level valuations.",
        },
        "teams": teams,
    }

    output = DATA_DIR / "oracle_public.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
