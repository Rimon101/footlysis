"""
Kelly Criterion and bankroll management utilities.
"""
from typing import Dict, List


def kelly_fraction(probability: float, decimal_odds: float) -> float:
    """
    Full Kelly Criterion stake fraction.
    f = (bp - q) / b
    where:  b = decimal_odds - 1 (net odds)
            p = model probability
            q = 1 - p
    """
    b = decimal_odds - 1.0
    p = probability
    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, round(f, 4))


def fractional_kelly(probability: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """Quarter Kelly is the professional standard – reduces variance dramatically."""
    return round(kelly_fraction(probability, decimal_odds) * fraction, 4)


def expected_value(probability: float, decimal_odds: float) -> float:
    """EV = (probability × decimal_odds) - 1"""
    return round(probability * decimal_odds - 1, 4)


def implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return round(1.0 / decimal_odds, 4)


def overround(home_odds: float, draw_odds: float, away_odds: float) -> float:
    """Calculate bookmaker margin (overround)."""
    total_implied = 1 / home_odds + 1 / draw_odds + 1 / away_odds
    return round((total_implied - 1) * 100, 2)


def edge_percentage(model_prob: float, decimal_odds: float) -> float:
    """
    % edge over the market.
    Positive = value bet.
    """
    market_prob = implied_probability(decimal_odds)
    return round((model_prob - market_prob) * 100, 2)


def fair_odds(probability: float) -> float:
    """Convert model probability to fair decimal odds."""
    if probability <= 0:
        return 0.0
    return round(1.0 / probability, 2)


def stake_recommendation(
    bankroll: float,
    probability: float,
    decimal_odds: float,
    fraction: float = 0.25,
    max_pct: float = 0.05,
) -> dict:
    """
    Full bankroll recommendation for a single bet.
    Caps stake at max_pct of bankroll regardless of Kelly.
    """
    fk = fractional_kelly(probability, decimal_odds, fraction)
    raw_stake = bankroll * fk
    capped_stake = min(raw_stake, bankroll * max_pct)
    ev = expected_value(probability, decimal_odds)
    edge = edge_percentage(probability, decimal_odds)

    ruin_risk = "Low"
    if fk > 0.1:
        ruin_risk = "Medium"
    if fk > 0.2:
        ruin_risk = "High - reduce fraction"

    return {
        "full_kelly": round(kelly_fraction(probability, decimal_odds), 4),
        "fractional_kelly": round(fk, 4),
        "stake_amount": round(capped_stake, 2),
        "expected_value": ev,
        "edge_pct": edge,
        "ruin_risk": ruin_risk,
        "fair_odds": fair_odds(probability),
        "market_prob": implied_probability(decimal_odds),
        "model_prob": round(probability, 4),
    }


def evaluate_value_bets(
    model_probs: dict,
    market_odds: dict,
    bankroll: float = 1000.0,
    min_edge: float = 2.0,
    fraction: float = 0.25,
) -> list:
    """
    Scan all available markets for value bets.

    model_probs: {"home": 0.52, "draw": 0.27, "away": 0.21, "over25": 0.58, "btts": 0.61}
    market_odds: {"home": 1.85, "draw": 3.40, "away": 4.50, "over25": 1.90, "btts": 1.75}
    min_edge: minimum edge % to flag as value bet

    Returns list of value bet dicts sorted by edge descending.
    """
    value_bets = []
    market_map = {
        "home": "Home Win",
        "draw": "Draw",
        "away": "Away Win",
        "over25": "Over 2.5 Goals",
        "under25": "Under 2.5 Goals",
        "btts": "BTTS Yes",
        "btts_no": "BTTS No",
    }

    for key, label in market_map.items():
        if key not in model_probs or key not in market_odds:
            continue

        prob = model_probs[key]
        odds = market_odds[key]
        if odds <= 1.0 or prob <= 0:
            continue

        edge = edge_percentage(prob, odds)
        rec = stake_recommendation(bankroll, prob, odds, fraction)
        is_value = edge >= min_edge

        value_bets.append({
            "market": label,
            "model_prob": rec["model_prob"],
            "market_prob": rec["market_prob"],
            "edge_pct": edge,
            "odds": odds,
            "fair_odds": rec["fair_odds"],
            "kelly_fraction": rec["fractional_kelly"],
            "stake_amount": rec["stake_amount"],
            "expected_value": rec["expected_value"],
            "is_value": is_value,
            "ruin_risk": rec["ruin_risk"],
        })

    return sorted(value_bets, key=lambda x: x["edge_pct"], reverse=True)
