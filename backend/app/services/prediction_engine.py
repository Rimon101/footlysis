"""
Prediction engine – orchestrates Poisson, Dixon-Coles, Elo, and Kelly.
"""
from typing import Dict, Optional, List, Tuple
import logging
import time
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


def calculate_squad_impact(players: List[Dict]) -> float:
    """
    Calculate the percentage drop in team strength due to injuries.
    Impact is based on xG/xA per 90 of missing players.
    """
    if not players:
        return 0.0
        
    total_impact = 0.0
    for p in players:
        if p.get("is_injured") or p.get("is_suspended"):
            # Attacking impact: xG + xA per 90 (contribution to scoring)
            # We cap individual player impact at 5% of team potential
            impact = min(0.05, (p.get("xg_per90", 0) or 0) + (p.get("xa_per90", 0) or 0))
            total_impact += impact
            
    # Max total penalty 15% (to avoid unrealistic drops if half the team is out)
    return min(0.15, total_impact)


def calculate_tactical_adjustment(home_stats: Dict, away_stats: Dict) -> float:
    """
    Adjust home win probability based on tactical style clash (PPDA).
    If a high-press team (low PPDA) faces a team with high turnover potential.
    """
    if not home_stats or not away_stats:
        return 0.0
        
    adjustment = 0.0
    
    h_ppda = home_stats.get("ppda", 0) or 0
    a_ppda = away_stats.get("ppda", 0) or 0
    
    # PPDA low = high intensity press. 
    # Example: If home team presses intensely (PPDA < 9) and away team is weak (lower ELO)
    if h_ppda > 0 and h_ppda < 9:
        adjustment += 0.02 # 2% boost for high press efficiency
        
    if a_ppda > 0 and a_ppda < 9:
        adjustment -= 0.02
        
    return adjustment


def calculate_market_probabilities(odds: Dict) -> Optional[Dict]:
    """Calculate implied probabilities from market odds (with margin removal)."""
    if not odds or not all(k in odds for k in ["home", "draw", "away"]):
        return None
        
    h_idx = 1.0 / odds["home"]
    d_idx = 1.0 / odds["draw"]
    a_idx = 1.0 / odds["away"]
    
    margin = (h_idx + d_idx + a_idx) - 1.0
    
    # Simple margin removal (proportional)
    total = h_idx + d_idx + a_idx
    return {
        "home": h_idx / total,
        "draw": d_idx / total,
        "away": a_idx / total
    }


def calculate_league_averages(historical_results: List[Dict]) -> Tuple[float, float]:
    """Calculate average home and away goals from historical data."""
    if not historical_results:
        return 1.5, 1.2  # Sensible defaults

    h_goals = [r.get("home_goals", 0) for r in historical_results if r.get("home_goals") is not None]
    a_goals = [r.get("away_goals", 0) for r in historical_results if r.get("away_goals") is not None]

    if not h_goals or not a_goals:
        return 1.5, 1.2

    return max(0.1, sum(h_goals) / len(h_goals)), max(0.1, sum(a_goals) / len(a_goals))


def calculate_h2h_adjustment(
    home_team: str,
    away_team: str,
    historical_results: List[Dict],
    max_h2h: int = 5
) -> float:
    """
    Calculate a small probability adjustment based on head-to-head records.
    Returns a delta to be added to home win prob and subtracted from away win prob.
    """
    if not historical_results:
        return 0.0

    # Filter for matches between these two teams
    h2h = []
    for r in historical_results:
        if (r.get("home_team") == home_team and r.get("away_team") == away_team) or \
           (r.get("home_team") == away_team and r.get("away_team") == home_team):
            h2h.append(r)

    if not h2h:
        return 0.0

    # Take most recent matches
    h2h.sort(key=lambda x: x.get("days_ago", 9999))
    recent_h2h = h2h[:max_h2h]

    home_points = 0
    for r in recent_h2h:
        if r["home_team"] == home_team:
            if (r.get("home_goals") or 0) > (r.get("away_goals") or 0): home_points += 3
            elif (r.get("home_goals") or 0) == (r.get("away_goals") or 0): home_points += 1
        else:
            if (r.get("away_goals") or 0) > (r.get("home_goals") or 0): home_points += 3
            elif (r.get("home_goals") or 0) == (r.get("away_goals") or 0): home_points += 1

    # Max points = max_h2h * 3. Scale to +/- 0.03 adjustment
    avg_pts = home_points / len(recent_h2h)
    adjustment = (avg_pts - 1.3) * 0.02  # 1.3 is 'average' points (approx draw/balanced)
    return round(max(-0.05, min(0.05, adjustment)), 4)


def predict_match(
    home_team_name: str,
    away_team_name: str,
    home_recent_matches: List[Dict],
    away_recent_matches: List[Dict],
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    home_elo: float = 1500.0,
    away_elo: float = 1500.0,
    home_players: Optional[List[Dict]] = None,
    away_players: Optional[List[Dict]] = None,
    home_stats: Optional[Dict] = None,
    away_stats: Optional[Dict] = None,
    market_odds: Optional[Dict] = None,
    historical_results: Optional[List[Dict]] = None,
    model: str = "ensemble_v2",
    bankroll: float = 1000.0,
) -> Dict:
    """
    Ensemble prediction engine (Phase 2).
    Blends Dixon-Coles (xG & Goals), Elo, Market Wisdom, and Squad/Tactical factors.
    """
    t0 = time.perf_counter()
    logger.info(f"predict_match (Phase 2): {home_team_name} vs {away_team_name}")

    # ── 1. League Averages ──────────────────────────────────────────────────
    league_home_avg, league_away_avg = calculate_league_averages(historical_results or [])

    # ── 2. Team Form calculation (for momentum / fallback lambdas) ──────────
    home_form = calculate_team_form(home_recent_matches, team_id=home_team_id or -1)
    away_form = calculate_team_form(away_recent_matches, team_id=away_team_id or -1)

    # Prepare lambda histories
    h_goals_hist = [m.get("goals_for", 0) or 0 for m in home_recent_matches]
    h_ga_hist = [m.get("goals_against", 0) or 0 for m in home_recent_matches]
    a_goals_hist = [m.get("goals_for", 0) or 0 for m in away_recent_matches]
    a_ga_hist = [m.get("goals_against", 0) or 0 for m in away_recent_matches]

    # Robust Fallback for Lambdas
    if not h_goals_hist or sum(h_goals_hist) == 0:
        h_goals_hist = [max(0.6, float(league_home_avg))] * 5
        h_ga_hist = [max(0.5, float(league_away_avg))] * 5
    if not a_goals_hist or sum(a_goals_hist) == 0:
        a_goals_hist = [max(0.5, float(league_away_avg))] * 5
        a_ga_hist = [max(0.6, float(league_home_avg))] * 5

    lambda_home, lambda_away = estimate_lambdas_from_history(
        h_goals_hist, h_ga_hist, a_goals_hist, a_ga_hist,
        league_home_avg, league_away_avg
    )

    # ── 3. Run Statistical Models ───────────────────────────────────────────
    probs_goals = None
    probs_xg = None

    # xG availability check
    has_xg = False
    if historical_results:
        xg_vals = [r.get("xg_home") for r in historical_results if r.get("xg_home") is not None and r.get("xg_home") > 0]
        if len(xg_vals) > len(historical_results) * 0.1:
            has_xg = True

    if historical_results and len(historical_results) >= 20:
        # Fit Goals model
        fit_g = fit_dixon_coles(historical_results, stat_type="goals")
        if fit_g:
            probs_goals = predict_from_fitted(fit_g, home_team_name, away_team_name)
        # Fit xG model
        if has_xg:
            fit_x = fit_dixon_coles(historical_results, stat_type="xg")
            if fit_x:
                probs_xg = predict_from_fitted(fit_x, home_team_name, away_team_name)

    # Fallbacks if fitting failed
    if not probs_goals:
        probs_goals = dc_match_probabilities(lambda_home, lambda_away)
    
    if not probs_xg:
        h_xg_hist = [m.get("xg_for", 0) or (m.get("goals_for", 0) or 0) for m in home_recent_matches]
        h_xga_hist = [m.get("xg_against", 0) or (m.get("goals_against", 0) or 0) for m in home_recent_matches]
        a_xg_hist = [m.get("xg_for", 0) or (m.get("goals_for", 0) or 0) for m in away_recent_matches]
        a_xga_hist = [m.get("xg_against", 0) or (m.get("goals_against", 0) or 0) for m in away_recent_matches]
        # Robustness for xG fallback
        if not h_xg_hist or sum(h_xg_hist) == 0: h_xg_hist = h_goals_hist
        if not a_xg_hist or sum(a_xg_hist) == 0: a_xg_hist = a_goals_hist
        lx_h, lx_a = estimate_lambdas_from_history(h_xg_hist, h_xga_hist, a_xg_hist, a_xga_hist, league_home_avg, league_away_avg)
        probs_xg = dc_match_probabilities(lx_h, lx_a)

    # ── 4. Elo & Market ───────────────────────────────────────────────────
    elo_home_p, elo_draw_p, elo_away_p = elo_win_probability(home_elo, away_elo)
    market_probs = calculate_market_probabilities(market_odds)

    # ── 5. Blending (Phase 2 Weights) ─────────────────────────────────────
    w_market = 0.10 if market_probs else 0.0
    w_xg = 0.35 if has_xg else 0.0
    w_goals = 0.25 if (has_xg and w_market > 0) else (0.60 if not has_xg else 0.30)
    w_elo = 0.20
    w_base = 1.0 - (w_market + w_xg + w_goals + w_elo)

    blend_home = (
        w_xg * probs_xg["prob_home_win"] +
        w_goals * probs_goals["prob_home_win"] +
        w_elo * elo_home_p +
        (w_market * market_probs["home"] if market_probs else 0) +
        w_base * (0.40)
    )
    blend_draw = (
        w_xg * probs_xg["prob_draw"] +
        w_goals * probs_goals["prob_draw"] +
        w_elo * elo_draw_p +
        (w_market * market_probs["draw"] if market_probs else 0) +
        w_base * (0.25)
    )
    blend_away = (
        w_xg * probs_xg["prob_away_win"] +
        w_goals * probs_goals["prob_away_win"] +
        w_elo * elo_away_p +
        (w_market * market_probs["away"] if market_probs else 0) +
        w_base * (0.35)
    )

    # ── 6. Advanced Adjustments ───────────────────────────────────────────
    h_momentum = momentum_score(home_form.get("form_last_5", ""))
    a_momentum = momentum_score(away_form.get("form_last_5", ""))
    momentum_delta = (h_momentum - a_momentum) * 0.005

    h_squad_impact = calculate_squad_impact(home_players) if home_players else 0.0
    a_squad_impact = calculate_squad_impact(away_players) if away_players else 0.0
    squad_delta = (a_squad_impact - h_squad_impact) 

    tactical_delta = calculate_tactical_adjustment(home_stats, away_stats)

    total_delta = momentum_delta + squad_delta + tactical_delta
    blend_home += total_delta * 0.5
    blend_away -= total_delta * 0.5
    
    # H2H factor
    h2h_adj = calculate_h2h_adjustment(home_team_name, away_team_name, historical_results or [])
    blend_home += h2h_adj
    blend_away -= h2h_adj

    # ── 7. Normalization & Markets ────────────────────────────────────────
    total = blend_home + blend_draw + blend_away
    if total > 0:
        p_h, p_d, p_a = blend_home/total, blend_draw/total, blend_away/total
    else:
        p_h, p_d, p_a = 0.33, 0.34, 0.33

    # Secondary markets: blend xG and Goal model outputs
    div = (w_xg + w_goals)
    p_over = (w_xg * probs_xg["prob_over25"] + w_goals * probs_goals["prob_over25"]) / div if div > 0 else 0.5
    p_btts = (w_xg * probs_xg["prob_btts_yes"] + w_goals * probs_goals["prob_btts_yes"]) / div if div > 0 else 0.5
    
    l_h = (w_xg * probs_xg["expected_goals_home"] + w_goals * probs_goals["expected_goals_home"]) / div if div > 0 else lambda_home
    l_a = (w_xg * probs_xg["expected_goals_away"] + w_goals * probs_goals["expected_goals_away"]) / div if div > 0 else lambda_away

    # ── 8. Value Bets ───────────────────────────────────────────────────
    final_probs = {
        "prob_home_win": round(p_h, 4), "prob_draw": round(p_d, 4), "prob_away_win": round(p_a, 4),
        "prob_over25": round(p_over, 4), "prob_under25": round(1 - p_over, 4),
        "prob_btts_yes": round(p_btts, 4), "prob_btts_no": round(1 - p_btts, 4)
    }
    value_bets = evaluate_value_bets(final_probs, market_odds, bankroll) if market_odds else []

    # ── 9. Confidence Score ─────────────────────────────────────────────
    # Base signal: how decisive the main probabilities are
    max_p = max(p_h, p_d, p_a)
    min_p = min(p_h, p_d, p_a)
    spread = max_p - min_p  # 0 (totally flat) -> ~0.7 (very decisive)

    # Normalise spread to 0–1 where 0 means 33/33/33, 1 means one side is near 100%
    spread_component = max(0.0, min(1.0, (spread - 0.05) / 0.65))

    # Agreement with Elo
    elo_disagreement = (abs(p_h - elo_home_p) + abs(p_d - elo_draw_p) + abs(p_a - elo_away_p)) / 3.0
    elo_component = 1.0 - max(0.0, min(1.0, elo_disagreement / 0.5))

    # Agreement with market (if available)
    if market_probs:
        m_home = market_probs["home"]
        m_draw = market_probs["draw"]
        m_away = market_probs["away"]
        m_disagreement = (abs(p_h - m_home) + abs(p_d - m_draw) + abs(p_a - m_away)) / 3.0
        market_component = 1.0 - max(0.0, min(1.0, m_disagreement / 0.5))
    else:
        market_component = 0.5  # neutral when no market data

    # Combine components (weighted)
    raw_conf = (
        0.5 * spread_component +
        0.25 * elo_component +
        0.25 * market_component
    )
    raw_conf = max(0.0, min(1.0, raw_conf))

    # Map to a user-friendly 20–95% range
    confidence = round(20 + raw_conf * 75, 1)

    elapsed = time.perf_counter() - t0
    logger.info(f"predict_match (Phase 2) completed in {elapsed:.2f}s")

    return {
        **final_probs,
        "expected_goals_home": round(l_h, 2),
        "expected_goals_away": round(l_a, 2),
        "expected_goals_total": round(l_h + l_a, 2),
        "confidence": confidence,
        "model_used": "ensemble_v2",
        "home_team": home_team_name,
        "away_team": away_team_name,
        "home_form": home_form,
        "away_form": away_form,
        "home_momentum": h_momentum,
        "away_momentum": a_momentum,
        "squad_impact_home": h_squad_impact,
        "squad_impact_away": a_squad_impact,
        "elo_home": elo_home_p,
        "elo_draw": elo_draw_p,
        "elo_away": elo_away_p,
        "value_bets": value_bets,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
