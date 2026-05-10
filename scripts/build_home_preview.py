"""Build the lightweight JSON payload used by the homepage previews."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INDEX = ROOT / "index.html"


def load_json(name: str, *, data_dir: Path = DATA) -> dict:
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def build_home_preview(site_root: Path = ROOT) -> dict:
    data_dir = site_root / "data"
    standings = load_json("standings.json", data_dir=data_dir)
    transactions = load_json("transactions.json", data_dir=data_dir)
    oracle = load_json("oracle_public.json", data_dir=data_dir)

    leaderboard = [
        {
            "rank": team.get("rank"),
            "team": team.get("team"),
            "total_pts": team.get("total_pts"),
            "pts_change": team.get("pts_change"),
        }
        for team in sorted(standings.get("teams", []), key=lambda team: team.get("rank") or 99)[:6]
    ]

    recent_transactions = [
        {
            "type": txn.get("type"),
            "team": txn.get("team"),
            "player": txn.get("player"),
        }
        for txn in (transactions.get("transactions") or [])[:9]
    ]

    oracle_teams = [
        {
            "team": team.get("team"),
            "oracle_rank": team.get("oracle_rank"),
            "total_value": team.get("total_value"),
            "mlb_value": team.get("mlb_value"),
            "farm_value": team.get("farm_value"),
            "avg_age": team.get("avg_age"),
            "scatter_move": {
                "previous_avg_age": team.get("scatter_move", {}).get("previous_avg_age"),
                "previous_total_value": team.get("scatter_move", {}).get("previous_total_value"),
            },
        }
        for team in oracle.get("teams", [])
    ]

    return {
        "generated": standings.get("generated"),
        "generated_at": standings.get("generated_at"),
        "week": standings.get("week"),
        "snapshot_date": oracle.get("snapshot_date"),
        "leaderboard": leaderboard,
        "transactions": recent_transactions,
        "oracle_teams": oracle_teams,
    }


def render_leaderboard_rows(leaderboard: list[dict]) -> str:
    rows = []
    for team in leaderboard:
        change = float(team.get("pts_change") or 0)
        change_class = " up" if change > 0 else " down" if change < 0 else ""
        change_text = f"+{change:.1f}" if change > 0 else f"{change:.1f}"
        rows.append(
            "\n".join(
                [
                    '      <div class="lb-row">',
                    f'        <div class="lb-rank">#{team.get("rank")}</div>',
                    f'        <div class="lb-team">{escape(str(team.get("team") or ""))}</div>',
                    f'        <div class="lb-pts">{float(team.get("total_pts") or 0):.1f}</div>',
                    f'        <div class="lb-change{change_class}">{change_text}</div>',
                    "      </div>",
                ]
            )
        )
    return "\n".join(rows)


def update_index_fallback(preview: dict, site_root: Path = ROOT) -> None:
    index = site_root / "index.html"
    html = index.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(?P<start>    <div class="lb-list" id="leaderboardList">\n)'
        r".*?"
        r'(?P<end>    </div>\n  </div>\n)',
        re.DOTALL,
    )
    updated, count = pattern.subn(
        rf'\g<start>{render_leaderboard_rows(preview.get("leaderboard") or [])}\n\g<end>',
        html,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not locate homepage leaderboard fallback block")
    index.write_text(updated, encoding="utf-8")


def write_home_preview(site_root: Path = ROOT) -> tuple[Path, Path]:
    preview = build_home_preview(site_root)
    output = site_root / "data" / "home_preview.json"
    output.write_text(
        json.dumps(preview, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    update_index_fallback(preview, site_root)
    return output, site_root / "index.html"


def main() -> None:
    write_home_preview()


if __name__ == "__main__":
    main()
