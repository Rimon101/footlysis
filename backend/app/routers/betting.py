from fastapi import APIRouter, Body
from typing import Dict, Optional
from app.schemas.schemas import KellyInput, KellyOut
from app.services.kelly_criterion import (
    stake_recommendation,
    evaluate_value_bets,
    overround,
    implied_probability,
    fair_odds,
    edge_percentage,
)

router = APIRouter(prefix="/betting", tags=["betting"])


@router.post("/kelly", response_model=KellyOut)
async def kelly_calculator(payload: KellyInput):
    """Calculate Kelly Criterion stake recommendation."""
    rec = stake_recommendation(
        bankroll=payload.bankroll,
        probability=payload.model_probability,
        decimal_odds=payload.decimal_odds,
        fraction=payload.fraction,
    )
    return KellyOut(**rec)


@router.post("/value-scan")
async def value_scan(
    model_probs: Dict[str, float] = Body(..., example={
        "home": 0.52, "draw": 0.27, "away": 0.21, "over25": 0.58, "btts": 0.61
    }),
    market_odds: Dict[str, float] = Body(..., example={
        "home": 1.85, "draw": 3.40, "away": 4.50, "over25": 1.90, "btts": 1.75
    }),
    bankroll: float = Body(1000.0, gt=0),
    min_edge: float = Body(2.0, ge=0),
    kelly_fraction: float = Body(0.25, ge=0.01, le=1.0),
):
    """Scan multiple markets for value bets."""
    value_bets = evaluate_value_bets(model_probs, market_odds, bankroll, min_edge, kelly_fraction)
    return {
        "value_bets": value_bets,
        "total_bets": len(value_bets),
        "value_bets_count": sum(1 for b in value_bets if b["is_value"]),
        "overround": overround(
            market_odds.get("home", 2.0),
            market_odds.get("draw", 3.5),
            market_odds.get("away", 3.5)
        ) if all(k in market_odds for k in ["home", "draw", "away"]) else None,
    }


@router.post("/odds-converter")
async def odds_converter(
    decimal_odds: float = Body(..., gt=1),
    model_probability: Optional[float] = Body(None, ge=0, le=1),
):
    """Convert odds and calculate edge."""
    result = {
        "decimal_odds": decimal_odds,
        "implied_probability": implied_probability(decimal_odds),
        "fair_odds": fair_odds(model_probability) if model_probability else None,
        "fractional_odds": f"{round(decimal_odds - 1, 2)}/1",
    }
    if model_probability is not None:
        result["edge_pct"] = edge_percentage(model_probability, decimal_odds)
        result["is_value"] = result["edge_pct"] > 0
    return result


@router.get("/overround")
async def calculate_overround(home: float, draw: float, away: float):
    """Calculate bookmaker margin."""
    margin = overround(home, draw, away)
    total_implied = round(1 / home + 1 / draw + 1 / away, 4)
    return {
        "overround_pct": margin,
        "total_implied_probability": total_implied,
        "home_implied": implied_probability(home),
        "draw_implied": implied_probability(draw),
        "away_implied": implied_probability(away),
        "note": "Lower overround = more fair market",
    }
