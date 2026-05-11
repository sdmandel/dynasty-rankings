"""Build the public Oracle payload for the static site.

This script only emits derived/public-facing summaries. It does not publish
the private rankings CSV or player-level valuation inputs.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from statistics import median


SITE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = SITE_ROOT / "data"
BOT_ROOT = SITE_ROOT.parent
RANKINGS_CSV = BOT_ROOT / "data" / "rankings_latest.csv"

SEASON = 2026
MID_AGE = 28.5
MID_VALUE = 25000

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

def load_json(name: str, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def load_previous_oracle_public(site_root: Path = SITE_ROOT) -> dict:
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:data/oracle_public.json"],
            cwd=site_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def load_team_registry(data_dir: Path = DEFAULT_DATA_DIR) -> tuple[dict[str, str], dict[str, str]]:
    data = load_json("team_registry.json", data_dir)
    alias_to_display: dict[str, str] = {}
    display_to_key: dict[str, str] = {}
    for row in data.get("teams", []):
        display_name = row["display_name"]
        display_to_key[display_name] = row["team_key"]
        for alias in row.get("aliases", []):
            alias_to_display[alias] = display_name
    return alias_to_display, display_to_key


def load_live_team_values(alias_to_display: dict[str, str], display_to_key: dict[str, str]) -> dict[str, dict]:
    if not RANKINGS_CSV.exists():
        raise FileNotFoundError(f"rankings_latest.csv not found at {RANKINGS_CSV}")

    accum: dict[str, dict] = {
        display_name: {"total_value": 0.0, "mlb_value": 0.0, "ages": []}
        for display_name in display_to_key
    }

    with RANKINGS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        for row in rows:
            owner = (row.get("Owned By") or "").strip()
            if not owner:
                continue
            team_name = alias_to_display.get(owner)
            if not team_name:
                continue

            try:
                score = float(row.get("Score") or 0)
            except (TypeError, ValueError):
                score = 0.0

            level = (row.get("Level") or "").strip().upper()
            positions = (row.get("Positions") or "").strip()
            is_mlb_active = level == "MLB" and bool(positions)

            accum[team_name]["total_value"] += score
            if is_mlb_active:
                accum[team_name]["mlb_value"] += score
                try:
                    age = float(row.get("Age") or 0)
                except (TypeError, ValueError):
                    age = 0.0
                if age > 0:
                    accum[team_name]["ages"].append(age)

    ranked = sorted(
        accum.items(),
        key=lambda item: (-item[1]["total_value"], item[0]),
    )

    result: dict[str, dict] = {}
    for idx, (team_name, values) in enumerate(ranked, start=1):
        total_value = round(values["total_value"], 1)
        mlb_value = round(values["mlb_value"], 1)
        avg_age = round(sum(values["ages"]) / len(values["ages"]), 1) if values["ages"] else 0.0
        result[team_name] = {
            "oracle_rank": idx,
            "total_value": total_value,
            "mlb_value": mlb_value,
            "farm_value": round(total_value - mlb_value, 1),
            "avg_age": avg_age,
        }
    return result


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
        elif manager.get("archetype") == "market watcher":
            manager_label = "trade-aware"
        elif manager.get("archetype") == "grinder":
            manager_label = "waiver churn"
        elif manager.get("archetype") == "waiver regular":
            manager_label = "waiver-active"
        elif manager.get("archetype") == "selective":
            manager_label = "selective manager"
        elif manager.get("archetype") == "holding steady":
            manager_label = "holding steady"
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
    tier = team["contention_tier"]
    gain_cat = team["pressure"]["gain_target"]["category"]
    gain_gap = team["pressure"]["gain_target"]["gap"]
    loss_cat = team["pressure"]["loss_risk"]["category"]
    loss_gap = team["pressure"]["loss_risk"]["gap"]
    farm_share = team["farm_share"]
    avg_age = team["avg_age"]
    pts_change = standings_row.get("pts_change")

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
        "pts_change": pts_change,
        "stock": stock,
        "summary": summary,
        "rank_delta": None,
        "tier_change": None,
        "farm_delta": None,
    }


def _quadrant_label(avg_age: float | None, total_value: float | None) -> str | None:
    if avg_age is None or total_value is None:
        return None
    if total_value >= MID_VALUE and avg_age < MID_AGE:
        return "REBUILDING"
    if total_value >= MID_VALUE and avg_age >= MID_AGE:
        return "WIN NOW"
    if total_value < MID_VALUE and avg_age < MID_AGE:
        return "NEEDS WORK"
    return "AGING OUT"


def derive_scatter_move(team: dict, previous_row: dict | None) -> dict:
    current_age = team["avg_age"]
    current_value = team["total_value"]
    previous_age = previous_row.get("avg_age") if previous_row else None
    previous_value = previous_row.get("total_value") if previous_row else None
    age_delta = round(current_age - previous_age, 2) if previous_age is not None else None
    value_delta = round(current_value - previous_value, 1) if previous_value is not None else None

    return {
        "previous_avg_age": previous_age,
        "previous_total_value": previous_value,
        "age_delta": age_delta,
        "value_delta": value_delta,
        "previous_quadrant": _quadrant_label(previous_age, previous_value),
        "current_quadrant": _quadrant_label(current_age, current_value),
    }


def export_oracle_public(site_root: Path = SITE_ROOT, output_path: Path | None = None) -> dict:
    global CATEGORIES
    data_dir = site_root / "data"
    standings = load_json("standings.json", data_dir)
    intelligence = load_json("league_intelligence.json", data_dir)
    managers = load_json("managers.json", data_dir)
    previous_payload = load_previous_oracle_public(site_root)
    alias_to_display, _display_to_key = load_team_registry(data_dir)
    value_input = load_live_team_values(alias_to_display, _display_to_key)

    standings_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in standings["teams"]}
    intel_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in intelligence["teams"]}
    manager_by_team = {alias_to_display.get(row["team"], row["team"]): row for row in managers["managers"]}
    previous_by_team = {
        row.get("team"): row
        for row in previous_payload.get("teams", [])
        if row.get("team")
    }
    median_total = median(team["total_value"] for team in value_input.values())

    CATEGORIES = CATEGORY_CODE_TO_LABEL
    teams: list[dict] = []
    for team_name, raw in sorted(value_input.items(), key=lambda item: item[1]["oracle_rank"]):
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
        team["scatter_move"] = derive_scatter_move(team, previous_by_team.get(team_name))
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
            "oracle_values": str(RANKINGS_CSV.relative_to(BOT_ROOT)),
        },
        "notes": {
            "privacy": "Private rankings CSV remains unpublished. This payload contains only derived/public summaries.",
            "oracle_window": "Oracle value = public team-level aggregate, not player-level valuations.",
        },
        "teams": teams,
    }

    output = output_path or (data_dir / "oracle_public.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    export_oracle_public()


if __name__ == "__main__":
    main()
