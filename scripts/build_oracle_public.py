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


def _category_points(categories: dict, labels: tuple[str, ...]) -> float:
    return sum(float(categories.get(label, {}).get("pts", 0)) for label in labels)


def _category_profile(categories: dict) -> dict:
    rows = [
        (label, float(info.get("pts", 0)))
        for label, info in categories.items()
    ]
    rows.sort(key=lambda item: (item[1], item[0]), reverse=True)
    strong = [label for label, pts in rows if pts >= 9.5]
    weak = [label for label, pts in rows if pts <= 3.5]
    spread = (rows[0][1] - rows[-1][1]) if rows else 0.0

    offense_score = _category_points(categories, ("R", "HR", "RBI", "SB", "OPS"))
    pitching_score = _category_points(categories, ("QS", "K", "ERA", "WHIP", "SVH"))
    power_score = _category_points(categories, ("HR", "RBI", "OPS"))
    speed_score = _category_points(categories, ("R", "SB"))
    ratio_score = _category_points(categories, ("ERA", "WHIP"))
    volume_score = _category_points(categories, ("QS", "K"))

    return {
        "rows": rows,
        "top": [label for label, _pts in rows[:3]],
        "strong": strong,
        "weak": weak,
        "spread": spread,
        "offense_score": offense_score,
        "pitching_score": pitching_score,
        "power_score": power_score,
        "speed_score": speed_score,
        "ratio_score": ratio_score,
        "volume_score": volume_score,
    }


def derive_public_archetypes(team: dict, manager: dict | None, standings_row: dict, median_total: float) -> list[str]:
    farm_share = team["farm_share"]
    avg_age = team["avg_age"]
    tier = team["contention_tier"]
    categories = standings_row.get("categories", {})
    profile = _category_profile(categories)
    svh_pts = float(categories.get("SVH", {}).get("pts", 0))
    sb_pts = float(categories.get("SB", {}).get("pts", 0))

    archetypes: list[str] = [tier]

    construction_label = None
    if tier == "rebuilding" and farm_share >= 0.24:
        construction_label = "farm-forward build"
    elif tier in {"fringe", "stagnating"} and farm_share >= 0.19 and avg_age <= 29.2:
        construction_label = "soft retool"
    elif avg_age >= 30.0 and farm_share <= 0.10:
        construction_label = "aging core"
    elif avg_age >= 29.8 and farm_share <= 0.15 and team["total_value"] >= median_total * 0.85:
        construction_label = "win-now veteran"
    elif farm_share >= 0.22:
        construction_label = "prospect stockpile"

    if construction_label:
        archetypes.append(construction_label)

    identity_candidates: list[str] = []
    if profile["spread"] <= 4.0 and len([label for label, pts in profile["rows"] if pts >= 6.0]) >= 8:
        identity_candidates.append("balanced build")
    if profile["ratio_score"] >= 19.0 and profile["volume_score"] <= 18.0:
        identity_candidates.append("ratio-first staff")
    if profile["volume_score"] >= 19.0:
        identity_candidates.append("volume arms")
    if profile["power_score"] >= 29.0:
        identity_candidates.append("power bat backbone")
    if profile["speed_score"] >= 18.0 and sb_pts >= 9.0:
        identity_candidates.append("speed pressure offense")
    if svh_pts >= 9.5:
        identity_candidates.append("bullpen-backed")
    if profile["spread"] >= 8.0 and len(profile["strong"]) >= 3 and len(profile["weak"]) >= 3:
        identity_candidates.append("high-variance build")
    if profile["offense_score"] - profile["pitching_score"] >= 7.0:
        identity_candidates.append("bat-first build")
    if profile["pitching_score"] - profile["offense_score"] >= 7.0:
        identity_candidates.append("pitching-led build")
    if profile["power_score"] <= 16.0 and float(categories.get("R", {}).get("pts", 0)) <= 4.0:
        identity_candidates.append("offense-starved")

    for label in identity_candidates:
        if label not in archetypes:
            archetypes.append(label)
            break

    manager_label = None
    if manager and len(archetypes) < 3:
        if manager.get("archetype") == "trader":
            manager_label = "trade-driven"
        elif manager.get("archetype") == "grinder":
            manager_label = "waiver churn"
        elif manager.get("archetype") == "asleep at the wheel":
            manager_label = "quiet roster"
    if manager_label and manager_label not in archetypes:
        archetypes.append(manager_label)

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
