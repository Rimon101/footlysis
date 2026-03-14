"""
Poisson Distribution Model for football match prediction.
Models goals as independent Poisson processes.
"""

import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, Tuple, List


def poisson_probability(lam: float, k: int) -> float:
    """P(X=k) where X ~ Poisson(lambda)"""
    return poisson.pmf(k, lam)


def build_score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 8
) -> np.ndarray:
    """
    Build an (max_goals+1) x (max_goals+1) probability matrix.
    matrix[i][j] = P(home=i, away=j)
    """
    matrix = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            matrix[i][j] = poisson_probability(lambda_home, i) * poisson_probability(lambda_away, j)
    return matrix


def calculate_match_probabilities(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 8
) -> Dict:
    """
    Calculate full match probability breakdown from lambda values.
    Returns win/draw/loss, over/under, BTTS, score matrix.
    """
    matrix = build_score_matrix(lambda_home, lambda_away, max_goals)

    prob_home_win = float(np.sum(np.tril(matrix, -1)))
    prob_draw = float(np.sum(np.diag(matrix)))
    prob_away_win = float(np.sum(np.triu(matrix, 1)))

    # Over/Under 2.5
    prob_over25 = 0.0
    prob_btts = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            if i + j > 2.5:
                prob_over25 += matrix[i][j]
            if i > 0 and j > 0:
                prob_btts += matrix[i][j]

    # Score matrix as dict
    score_dict = {}
    for i in range(min(5, max_goals + 1)):
        for j in range(min(5, max_goals + 1)):
            score_dict[f"{i}-{j}"] = round(float(matrix[i][j]), 4)

    # Top 5 most likely scores
    all_scores = [(f"{i}-{j}", matrix[i][j]) for i in range(max_goals + 1) for j in range(max_goals + 1)]
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
        "expected_goals_home": round(lambda_home, 3),
        "expected_goals_away": round(lambda_away, 3),
        "expected_goals_total": round(lambda_home + lambda_away, 3),
        "score_matrix": score_dict,
        "top5_scores": top5,
        "most_likely_score": top5[0]["score"] if top5 else "1-1",
    }


def estimate_lambdas_from_history(
    home_scored: List[float],
    home_conceded: List[float],
    away_scored: List[float],
    away_conceded: List[float],
    league_home_avg: float = 1.5,
    league_away_avg: float = 1.2,
    home_advantage: float = 0.25,
) -> Tuple[float, float]:
    """
    Estimate lambda_home and lambda_away from team historical stats.

    Uses attack/defence strength ratio method:
      AttackStrength = team_avg_scored / league_avg_scored
      DefenceStrength = team_avg_conceded / league_avg_conceded
      lambda_home = home_attack * away_defence * league_home_avg * home_advantage_factor
    """
    if not home_scored or not away_scored:
        return league_home_avg, league_away_avg

    # Home team attack and defence
    h_avg_scored = sum(home_scored) / max(1, len(home_scored))
    h_avg_conceded = sum(home_conceded) / max(1, len(home_conceded))
    home_attack_strength = h_avg_scored / max(0.1, league_home_avg)
    home_defence_strength = h_avg_conceded / max(0.1, league_away_avg)
 
    # Away team attack and defence
    a_avg_scored = sum(away_scored) / max(1, len(away_scored))
    a_avg_conceded = sum(away_conceded) / max(1, len(away_conceded))
    away_attack_strength = a_avg_scored / max(0.1, league_away_avg)
    away_defence_strength = a_avg_conceded / max(0.1, league_home_avg)
 
    lambda_home = home_attack_strength * away_defence_strength * league_home_avg * (1 + home_advantage)
    lambda_away = away_attack_strength * home_defence_strength * league_away_avg

    # Clamp to realistic values
    lambda_home = max(0.3, min(lambda_home, 5.0))
    lambda_away = max(0.3, min(lambda_away, 5.0))

    return round(lambda_home, 4), round(lambda_away, 4)


# ─── Team Strength Fitting ─────────────────────────────────────────────────────

def fit_team_strengths(results: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    MLE fit of attack/defence parameters for each team given match results.
    results: list of dicts with keys: home_team, away_team, home_goals, away_goals
    """
    teams = list(set([r["home_team"] for r in results] + [r["away_team"] for r in results]))
    n_teams = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}

    def neg_log_likelihood(params):
        # params layout: [attack_0..n, defence_0..n, home_advantage]
        attack = params[:n_teams]
        defence = params[n_teams:2 * n_teams]
        home_adv = params[2 * n_teams]
        ll = 0.0
        for r in results:
            i = team_idx[r["home_team"]]
            j = team_idx[r["away_team"]]
            lam_h = np.exp(home_adv + attack[i] - defence[j])
            lam_a = np.exp(attack[j] - defence[i])
            ll -= poisson.logpmf(r["home_goals"], lam_h)
            ll -= poisson.logpmf(r["away_goals"], lam_a)
        return ll

    x0 = np.zeros(2 * n_teams + 1)
    x0[2 * n_teams] = 0.25  # initial home advantage

    # Constraint: sum of attack params = 0
    constraints = [{"type": "eq", "fun": lambda p: np.sum(p[:n_teams])}]
    bounds = [(-3, 3)] * (2 * n_teams) + [(0, 1)]

    result = minimize(
        neg_log_likelihood,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500},
    )

    strengths = {}
    if result.success:
        attack = result.x[:n_teams]
        defence = result.x[n_teams:2 * n_teams]
        home_adv = result.x[2 * n_teams]
        for t in teams:
            i = team_idx[t]
            strengths[t] = {
                "attack": round(float(attack[i]), 4),
                "defence": round(float(defence[i]), 4),
                "home_advantage": round(float(home_adv), 4),
            }
    return strengths
