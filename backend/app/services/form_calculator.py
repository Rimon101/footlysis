"""
Form calculator – rolling averages and time-decay weighted metrics.
"""

from typing import List, Dict, Optional
import numpy as np
from datetime import datetime, timezone


def form_string(results: List[str]) -> str:
    """Convert list of 'W','D','L' to display string like 'WWDLW'."""
    return "".join(results[-10:])


def rolling_average(values: List[float], window: int = 5) -> float:
    """Simple rolling average of last N values."""
    if not values:
        return 0.0
    recent = values[-window:]
    return round(float(np.mean(recent)), 3)


def decay_weighted_average(
    values: List[float],
    dates: Optional[List[datetime]] = None,
    xi: float = 0.0018,
) -> float:
    """
    Exponentially decay-weighted average.
    More recent matches weigh more.
    """
    if not values:
        return 0.0

    if dates:
        now = datetime.now(timezone.utc)
        days_ago = [(now - (d if d.tzinfo else d.replace(tzinfo=timezone.utc))).days for d in dates]
        weights = [np.exp(-xi * max(0, d)) for d in days_ago]
    else:
        # Use index-based decay if no dates provided
        n = len(values)
        weights = [np.exp(-xi * (n - 1 - i) * 30) for i in range(n)]  # assume 30d apart

    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(v * w for v, w in zip(values, weights))
    return round(weighted_sum / total_weight, 3)


def calculate_team_form(recent_matches: List[Dict], team_id: int) -> Dict:
    """
    Calculate comprehensive form metrics for a team from recent match data.

    Each match dict expected keys:
        home_team_id, away_team_id, home_goals, away_goals,
        xg_home, xg_away, match_date
    """
    results = []
    goals_scored = []
    goals_conceded = []
    xg_for = []
    xg_against = []
    dates = []

    for m in recent_matches:
        is_home = m.get("home_team_id") == team_id

        if is_home:
            scored = m.get("home_goals", 0) or 0
            conceded = m.get("away_goals", 0) or 0
            xgf = m.get("xg_home", 0) or 0
            xga = m.get("xg_away", 0) or 0
        else:
            scored = m.get("away_goals", 0) or 0
            conceded = m.get("home_goals", 0) or 0
            xgf = m.get("xg_away", 0) or 0
            xga = m.get("xg_home", 0) or 0

        if scored > conceded:
            results.append("W")
        elif scored == conceded:
            results.append("D")
        else:
            results.append("L")

        goals_scored.append(scored)
        goals_conceded.append(conceded)
        xg_for.append(xgf)
        xg_against.append(xga)

        if m.get("match_date"):
            d = m["match_date"]
            if isinstance(d, str):
                try:
                    d = datetime.fromisoformat(d)
                except ValueError:
                    d = datetime.now(timezone.utc)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            dates.append(d)

    form_5 = form_string(results[-5:])
    form_10 = form_string(results[-10:])

    wins = results.count("W")
    draws = results.count("D")
    losses = results.count("L")
    n = len(results)

    pts = wins * 3 + draws
    ppg = round(pts / n, 2) if n else 0.0

    clean_sheets = sum(1 for c in goals_conceded if c == 0)
    btts_count = sum(1 for s, c in zip(goals_scored, goals_conceded) if s > 0 and c > 0)

    return {
        "form_last_5": form_5,
        "form_last_10": form_10,
        "matches": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points_per_game": ppg,
        "goals_per_game": round(sum(goals_scored) / n, 2) if n else 0.0,
        "conceded_per_game": round(sum(goals_conceded) / n, 2) if n else 0.0,
        "clean_sheet_pct": round(clean_sheets / n * 100, 1) if n else 0.0,
        "btts_pct": round(btts_count / n * 100, 1) if n else 0.0,
        "rolling5_goals_for": rolling_average(goals_scored, 5),
        "rolling5_goals_against": rolling_average(goals_conceded, 5),
        "rolling10_goals_for": rolling_average(goals_scored, 10),
        "rolling10_goals_against": rolling_average(goals_conceded, 10),
        "rolling5_xg_for": rolling_average(xg_for, 5),
        "rolling5_xg_against": rolling_average(xg_against, 5),
        "rolling10_xg_for": rolling_average(xg_for, 10),
        "rolling10_xg_against": rolling_average(xg_against, 10),
        "decay_weighted_xg_for": decay_weighted_average(xg_for, dates if dates else None),
        "decay_weighted_xg_against": decay_weighted_average(xg_against, dates if dates else None),
    }


def momentum_score(form_last_5: str) -> float:
    """
    Simple momentum score from -5 to +5.
    W=+1, D=0, L=-1.
    """
    score = 0.0
    weights = [1.0, 1.2, 1.4, 1.6, 2.0]  # more weight to recent
    for i, ch in enumerate(reversed(form_last_5[-5:])):
        w = weights[i] if i < len(weights) else 1.0
        if ch == "W":
            score += w
        elif ch == "L":
            score -= w
    return round(score, 2)
