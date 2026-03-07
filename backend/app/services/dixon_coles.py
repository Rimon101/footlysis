"""
Dixon-Coles Model (1997) for football match prediction.
Extends Poisson with a low-score correction factor (rho) that
adjusts probabilities for 0-0, 1-0, 0-1, 1-1 scorelines.
Also incorporates time-decay weighting so recent matches matter more.
"""

import logging
import math
import time
from typing import Dict, List, Tuple, Optional

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from scipy.special import gammaln

logger = logging.getLogger(__name__)


# ─── Low-Score Correction (Dixon-Coles tau) ─────────────────────────────────

def tau(home_goals: int, away_goals: int, lam_home: float, lam_away: float, rho: float) -> float:
    """
    Correction factor for low scoring outcomes.
    rho ≈ -0.13 (slightly negative dependency between home and away goals)
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - lam_home * lam_away * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + lam_away * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + lam_home * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0


def dc_probability(home_goals: int, away_goals: int, lam_home: float, lam_away: float, rho: float = -0.13) -> float:
    """
    Dixon-Coles corrected probability for a specific scoreline.
    """
    base = poisson.pmf(home_goals, lam_home) * poisson.pmf(away_goals, lam_away)
    correction = tau(home_goals, away_goals, lam_home, lam_away, rho)
    return max(base * correction, 1e-10)


def build_dc_matrix(
    lam_home: float,
    lam_away: float,
    rho: float = -0.13,
    max_goals: int = 8
) -> np.ndarray:
    """Build full probability matrix using Dixon-Coles correction."""
    matrix = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            matrix[i][j] = dc_probability(i, j, lam_home, lam_away, rho)

    # Normalise to sum to 1
    total = matrix.sum()
    if total > 0:
        matrix /= total
    return matrix


def dc_match_probabilities(
    lam_home: float,
    lam_away: float,
    rho: float = -0.13,
    max_goals: int = 8
) -> Dict:
    """
    Full probability breakdown using Dixon-Coles model.
    """
    matrix = build_dc_matrix(lam_home, lam_away, rho, max_goals)

    prob_home_win = float(np.sum(np.tril(matrix, -1)))
    prob_draw = float(np.sum(np.diag(matrix)))
    prob_away_win = float(np.sum(np.triu(matrix, 1)))

    prob_over25 = 0.0
    prob_btts = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            if i + j > 2.5:
                prob_over25 += matrix[i][j]
            if i > 0 and j > 0:
                prob_btts += matrix[i][j]

    score_dict = {}
    all_scores = []
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            score_dict[f"{i}-{j}"] = round(float(matrix[i][j]), 4)
            all_scores.append((f"{i}-{j}", float(matrix[i][j])))

    all_scores.sort(key=lambda x: x[1], reverse=True)
    top5 = [{"score": s, "probability": round(p, 4)} for s, p in all_scores[:5]]

    return {
        "prob_home_win": round(prob_home_win, 4),
        "prob_draw": round(prob_draw, 4),
        "prob_away_win": round(prob_away_win, 4),
        "prob_over25": round(prob_over25, 4),
        "prob_under25": round(1 - prob_over25, 4),
        "prob_btts_yes": round(prob_btts, 4),
        "prob_btts_no": round(1 - prob_btts, 4),
        "expected_goals_home": round(lam_home, 3),
        "expected_goals_away": round(lam_away, 3),
        "expected_goals_total": round(lam_home + lam_away, 3),
        "score_matrix": score_dict,
        "top5_scores": top5,
        "most_likely_score": top5[0]["score"] if top5 else "1-1",
    }


# ─── Time-Decay Weighting ─────────────────────────────────────────────────────

def time_decay_weight(days_ago: int, xi: float = 0.0018) -> float:
    """
    Exponential time decay: w = exp(-xi * days_ago)
    Default xi=0.0018 means ~50% weight at ~385 days.
    """
    return math.exp(-xi * max(0, days_ago))


# ─── MLE Fitting with Time-Decay ─────────────────────────────────────────────

def fit_dixon_coles(results: List[Dict], xi: float = 0.0018) -> Optional[Dict]:
    """
    Fit Dixon-Coles parameters using MLE with time-decay weighting.

    results: list of dicts:
        - home_team: str
        - away_team: str
        - home_goals: int
        - away_goals: int
        - days_ago: int  (how many days ago this match was played)

    Returns:
        dict with keys: attack_{team}, defence_{team}, home_advantage, rho
    """
    teams = sorted(set([r["home_team"] for r in results] + [r["away_team"] for r in results]))
    n = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}
    logger.info(f"Dixon-Coles fitting: {n} teams, {len(results)} matches, {2*n+2} parameters")
    t0 = time.perf_counter()

    weights = [time_decay_weight(r.get("days_ago", 0), xi) for r in results]
    w_arr = np.array(weights)
    
    i_idx = np.array([team_idx[r["home_team"]] for r in results])
    j_idx = np.array([team_idx[r["away_team"]] for r in results])
    hg = np.array([r["home_goals"] for r in results], dtype=int)
    ag = np.array([r["away_goals"] for r in results], dtype=int)
    
    log_k_fact_h = gammaln(hg + 1)
    log_k_fact_a = gammaln(ag + 1)
    
    mask_00 = (hg == 0) & (ag == 0)
    mask_10 = (hg == 1) & (ag == 0)
    mask_01 = (hg == 0) & (ag == 1)
    mask_11 = (hg == 1) & (ag == 1)

    def neg_log_likelihood(params):
        attack = params[:n]
        defence = params[n:2 * n]
        home_adv = params[2 * n]
        rho = params[2 * n + 1]

        lam_h = np.exp(home_adv + attack[i_idx] - defence[j_idx])
        lam_a = np.exp(attack[j_idx] - defence[i_idx])

        t = np.ones_like(hg, dtype=float)
        t[mask_00] = 1.0 - lam_h[mask_00] * lam_a[mask_00] * rho
        t[mask_10] = 1.0 + lam_a[mask_10] * rho
        t[mask_01] = 1.0 + lam_h[mask_01] * rho
        t[mask_11] = 1.0 - rho
        
        log_base_h = hg * np.log(lam_h) - lam_h - log_k_fact_h
        log_base_a = ag * np.log(lam_a) - lam_a - log_k_fact_a
        
        p_total = np.maximum(t, 1e-10)
        log_p = log_base_h + log_base_a + np.log(p_total)
        
        return -np.sum(w_arr * log_p)

    x0 = np.zeros(2 * n + 2)
    x0[2 * n] = 0.25     # home advantage
    x0[2 * n + 1] = -0.13  # rho

    constraints = [{"type": "eq", "fun": lambda p: np.sum(p[:n])}]
    bounds = [(-3, 3)] * (2 * n) + [(0, 1.5), (-0.99, 0.99)]

    try:
        result = minimize(
            neg_log_likelihood,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 100, "ftol": 1e-5},
        )

        elapsed = time.perf_counter() - t0
        logger.info(f"Dixon-Coles optimization finished in {elapsed:.2f}s (success={result.success}, nit={result.nit})")
        if not result.success:
            return None

        params_out = {}
        for t in teams:
            i = team_idx[t]
            params_out[f"attack_{t}"] = round(float(result.x[i]), 4)
            params_out[f"defence_{t}"] = round(float(result.x[n + i]), 4)
        params_out["home_advantage"] = round(float(result.x[2 * n]), 4)
        params_out["rho"] = round(float(result.x[2 * n + 1]), 4)
        params_out["teams"] = teams
        return params_out

    except Exception:
        return None


def predict_from_fitted(
    params: Dict,
    home_team: str,
    away_team: str,
    rho: Optional[float] = None,
) -> Optional[Dict]:
    """
    Use fitted Dixon-Coles params to predict a specific match.
    """
    if f"attack_{home_team}" not in params or f"attack_{away_team}" not in params:
        return None

    home_adv = params.get("home_advantage", 0.25)
    _rho = rho if rho is not None else params.get("rho", -0.13)

    lam_home = math.exp(
        home_adv + params[f"attack_{home_team}"] - params[f"defence_{away_team}"]
    )
    lam_away = math.exp(
        params[f"attack_{away_team}"] - params[f"defence_{home_team}"]
    )

    return dc_match_probabilities(lam_home, lam_away, _rho)


# ─── Elo Rating System ────────────────────────────────────────────────────────

def elo_expected(rating_a: float, rating_b: float) -> float:
    """Expected score for team A against team B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def elo_update(rating: float, expected: float, actual: float, k: float = 32) -> float:
    """Update Elo rating after a match."""
    return round(rating + k * (actual - expected), 2)


def update_elo_ratings(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    k: float = 32,
    home_advantage: float = 100,
) -> Tuple[float, float]:
    """
    Update both teams' Elo ratings after a match result.
    home_advantage: extra Elo points added to home team's effective rating.
    """
    adj_home = home_rating + home_advantage
    exp_home = elo_expected(adj_home, away_rating)
    exp_away = 1 - exp_home

    if home_goals > away_goals:
        actual_home, actual_away = 1.0, 0.0
    elif home_goals == away_goals:
        actual_home, actual_away = 0.5, 0.5
    else:
        actual_home, actual_away = 0.0, 1.0

    new_home = elo_update(home_rating, exp_home, actual_home, k)
    new_away = elo_update(away_rating, exp_away, actual_away, k)
    return new_home, new_away


def elo_win_probability(home_elo: float, away_elo: float, home_advantage: float = 100) -> Tuple[float, float, float]:
    """
    Estimate win/draw/loss probabilities from Elo ratings.
    Draw probability is approximated.
    """
    exp_home = elo_expected(home_elo + home_advantage, away_elo)
    exp_away = 1 - exp_home

    # Approximate draw probability based on closeness of ratings
    rating_diff = abs(home_elo + home_advantage - away_elo)
    draw_prob = max(0.1, 0.3 - 0.001 * rating_diff)

    home_win = exp_home * (1 - draw_prob)
    away_win = exp_away * (1 - draw_prob)

    return round(home_win, 4), round(draw_prob, 4), round(away_win, 4)
