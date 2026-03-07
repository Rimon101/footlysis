import time
import random
import logging
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

def time_decay_weight(days_ago: int, xi: float = 0.0018) -> float:
    return math.exp(-xi * max(0, days_ago))

def fit_dixon_coles_fast(results, xi: float = 0.0018):
    teams = sorted(set([r["home_team"] for r in results] + [r["away_team"] for r in results]))
    n = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}
    
    weights = [time_decay_weight(r.get("days_ago", 0), xi) for r in results]
    
    i_idx = np.array([team_idx[r["home_team"]] for r in results])
    j_idx = np.array([team_idx[r["away_team"]] for r in results])
    w_arr = np.array(weights)
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

    t0 = time.time()
    result = minimize(
        neg_log_likelihood,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 100, "ftol": 1e-5},
    )
    print(f"Fast optimization finished in {time.time() - t0:.4f}s")
    return result

def main():
    teams = [f"Team_{i}" for i in range(20)]
    results = []
    
    # Generate 200 random matches
    for _ in range(200):
        t1, t2 = random.sample(teams, 2)
        results.append({
            "home_team": t1,
            "away_team": t2,
            "home_goals": random.randint(0, 4),
            "away_goals": random.randint(0, 3),
            "days_ago": random.randint(0, 365)
        })

    print(f"Starting fitting for {len(teams)} teams and {len(results)} matches")
    fit = fit_dixon_coles_fast(results)

if __name__ == "__main__":
    main()
