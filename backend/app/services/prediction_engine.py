"""
Prediction engine – orchestrates Poisson, Dixon-Coles, Elo, and Kelly.
"""
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.services.dixon_coles import (
    dc_match_probabilities,
    fit_dixon_coles,
    predict_from_fitted,
    elo_win_probability,
)
from app.services.poisson_model import (
    calculate_match_probabilities,
    estimate_lambdas_from_history,
)
from app.services.kelly_criterion import evaluate_value_bets
from app.services.form_calculator import calculate_team_form, momentum_score


def predict_match(
    home_team_name: str,
    away_team_name: str,
    home_recent_matches: List[Dict],
    away_recent_matches: List[Dict],
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    home_elo: float = 1500.0,
    away_elo: float = 1500.0,
    market_odds: Optional[Dict] = None,
    historical_results: Optional[List[Dict]] = None,
    model: str = "dixon_coles",
    bankroll: float = 1000.0,
) -> Dict:
    """
    Full prediction pipeline for a single match.

    Returns comprehensive prediction dict including:
    - win/draw/loss probs
    - xG projections
    - score matrix
    - value bets (if market_odds provided)
    - form analysis
    - confidence score
    """

    t0 = time.perf_counter()
    logger.info(f"predict_match: {home_team_name} vs {away_team_name} (model={model})")

    # ── 1. Team Form ──────────────────────────────────────────────────────────
    home_form = calculate_team_form(home_recent_matches, team_id=home_team_id or -1)
    away_form = calculate_team_form(away_recent_matches, team_id=away_team_id or -1)

    # ── 2. Estimate Lambdas ───────────────────────────────────────────────────
    league_home_avg = 1.52
    league_away_avg = 1.18

    home_scored_hist = [m.get("goals_for", 0) or 0 for m in home_recent_matches]
    home_conceded_hist = [m.get("goals_against", 0) or 0 for m in home_recent_matches]
    away_scored_hist = [m.get("goals_for", 0) or 0 for m in away_recent_matches]
    away_conceded_hist = [m.get("goals_against", 0) or 0 for m in away_recent_matches]

    # Robust fallback: avoid zero-filled histories collapsing all lambdas to 0.30.
    # If there is no usable history, fall back to league baselines (home advantage preserved).
    if not home_scored_hist or sum(home_scored_hist) == 0:
        fallback_for = home_form.get("rolling5_xg_for") or league_home_avg
        fallback_against = home_form.get("rolling5_xg_against") or league_away_avg
        home_scored_hist = [max(0.6, float(fallback_for))] * 5
        home_conceded_hist = [max(0.5, float(fallback_against))] * 5

    if not away_scored_hist or sum(away_scored_hist) == 0:
        fallback_for = away_form.get("rolling5_xg_for") or league_away_avg
        fallback_against = away_form.get("rolling5_xg_against") or league_home_avg
        away_scored_hist = [max(0.5, float(fallback_for))] * 5
        away_conceded_hist = [max(0.6, float(fallback_against))] * 5

    lambda_home, lambda_away = estimate_lambdas_from_history(
        home_scored_hist, home_conceded_hist,
        away_scored_hist, away_conceded_hist,
        league_home_avg, league_away_avg,
    )

    # ── 3. Run Selected Model ─────────────────────────────────────────────────
    fitted_probs = None

    if model == "dixon_coles" and historical_results and len(historical_results) >= 20:
        logger.info(f"Fitting Dixon-Coles on {len(historical_results)} historical matches...")
        fit = fit_dixon_coles(historical_results)
        if fit:
            fitted_probs = predict_from_fitted(fit, home_team_name, away_team_name)

    if fitted_probs:
        probs = fitted_probs
    elif model == "dixon_coles":
        probs = dc_match_probabilities(lambda_home, lambda_away)
    else:
        probs = calculate_match_probabilities(lambda_home, lambda_away)

    # ── 4. Blend with Elo ─────────────────────────────────────────────────────
    elo_home, elo_draw, elo_away = elo_win_probability(home_elo, away_elo)

    # Weighted blend: 75% model, 25% Elo
    blend_home = round(0.75 * probs["prob_home_win"] + 0.25 * elo_home, 4)
    blend_draw = round(0.75 * probs["prob_draw"] + 0.25 * elo_draw, 4)
    blend_away = round(0.75 * probs["prob_away_win"] + 0.25 * elo_away, 4)

    # Renormalise
    total = blend_home + blend_draw + blend_away
    if total > 0:
        blend_home = round(blend_home / total, 4)
        blend_draw = round(blend_draw / total, 4)
        blend_away = round(1 - blend_home - blend_draw, 4)

    probs["prob_home_win"] = blend_home
    probs["prob_draw"] = blend_draw
    probs["prob_away_win"] = blend_away

    # ── 5. Momentum Adjustment ───────────────────────────────────────────────
    home_momentum = momentum_score(home_form.get("form_last_5", ""))
    away_momentum = momentum_score(away_form.get("form_last_5", ""))
    momentum_delta = (home_momentum - away_momentum) * 0.005

    probs["prob_home_win"] = round(min(0.95, max(0.02, probs["prob_home_win"] + momentum_delta)), 4)
    probs["prob_away_win"] = round(min(0.95, max(0.02, probs["prob_away_win"] - momentum_delta)), 4)

    # ── 6. Value Bets ─────────────────────────────────────────────────────────
    value_bets = []
    if market_odds:
        model_probs_map = {
            "home": probs["prob_home_win"],
            "draw": probs["prob_draw"],
            "away": probs["prob_away_win"],
            "over25": probs["prob_over25"],
            "under25": probs["prob_under25"],
            "btts": probs["prob_btts_yes"],
            "btts_no": probs["prob_btts_no"],
        }
        value_bets = evaluate_value_bets(model_probs_map, market_odds, bankroll)

    # ── 7. Confidence Score ───────────────────────────────────────────────────
    max_prob = max(probs["prob_home_win"], probs["prob_draw"], probs["prob_away_win"])
    # Scale confidence: 33% = 0, 90% = 100%
    confidence = round(min(100, max(0, (max_prob - 0.33) / 0.57 * 100)), 1)

    elapsed = time.perf_counter() - t0
    logger.info(f"predict_match completed in {elapsed:.2f}s")

    return {
        **probs,
        "model_used": model,
        "home_team": home_team_name,
        "away_team": away_team_name,
        "home_form": home_form,
        "away_form": away_form,
        "home_momentum": home_momentum,
        "away_momentum": away_momentum,
        "elo_home": elo_home,
        "elo_draw": elo_draw,
        "elo_away": elo_away,
        "value_bets": value_bets,
        "confidence": confidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
