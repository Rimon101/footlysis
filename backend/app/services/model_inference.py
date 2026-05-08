"""
Inference helper for optional XGBoost 1X2 model.

Safe-by-default:
- If model artifacts are missing or xgboost is unavailable, returns None.
- Prediction engine can fallback to existing ensemble output.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Optional


MODEL_PATH = Path("models/xgb_1x2.json")
FEATURE_PATH = Path("models/xgb_1x2.features.json")

_model = None
_feature_columns = None


def _load_model():
    global _model, _feature_columns
    if _model is not None and _feature_columns is not None:
        return _model, _feature_columns
    if not MODEL_PATH.exists() or not FEATURE_PATH.exists():
        return None, None
    try:
        import xgboost as xgb  # type: ignore
        _model = xgb.Booster()
        _model.load_model(MODEL_PATH.as_posix())
        meta = json.loads(FEATURE_PATH.read_text(encoding="utf-8"))
        _feature_columns = meta.get("feature_columns", [])
        return _model, _feature_columns
    except Exception:
        return None, None


def _safe(v, default=0.0):
    return default if v is None else float(v)


def build_feature_vector(
    home_elo: float,
    away_elo: float,
    home_stats: Optional[Dict],
    away_stats: Optional[Dict],
    market_odds: Optional[Dict],
) -> Dict[str, float]:
    market_odds = market_odds or {}
    home_stats = home_stats or {}
    away_stats = away_stats or {}
    return {
        "home_elo": _safe(home_elo, 1500.0),
        "away_elo": _safe(away_elo, 1500.0),
        "home_ppda": _safe(home_stats.get("ppda")),
        "away_ppda": _safe(away_stats.get("ppda")),
        "home_goals_scored": _safe(home_stats.get("goals_scored")),
        "home_goals_conceded": _safe(home_stats.get("goals_conceded")),
        "away_goals_scored": _safe(away_stats.get("goals_scored")),
        "away_goals_conceded": _safe(away_stats.get("goals_conceded")),
        "home_xg_for": _safe(home_stats.get("xg_for")),
        "home_xg_against": _safe(home_stats.get("xg_against")),
        "away_xg_for": _safe(away_stats.get("xg_for")),
        "away_xg_against": _safe(away_stats.get("xg_against")),
        "home_shots_per_game": _safe(home_stats.get("shots_per_game")),
        "home_shots_on_target_pct": _safe(home_stats.get("shots_on_target_pct")),
        "home_big_chances_created": _safe(home_stats.get("big_chances_created")),
        "home_shot_conversion_rate": _safe(home_stats.get("shot_conversion_rate")),
        "home_clean_sheet_pct": _safe(home_stats.get("clean_sheet_pct")),
        "home_btts_pct": _safe(home_stats.get("btts_pct")),
        "away_shots_per_game": _safe(away_stats.get("shots_per_game")),
        "away_shots_on_target_pct": _safe(away_stats.get("shots_on_target_pct")),
        "away_big_chances_created": _safe(away_stats.get("big_chances_created")),
        "away_shot_conversion_rate": _safe(away_stats.get("shot_conversion_rate")),
        "away_clean_sheet_pct": _safe(away_stats.get("clean_sheet_pct")),
        "away_btts_pct": _safe(away_stats.get("btts_pct")),
        "home_home_goals_scored": _safe(home_stats.get("home_goals_scored")),
        "home_home_goals_conceded": _safe(home_stats.get("home_goals_conceded")),
        "home_away_goals_scored": _safe(home_stats.get("away_goals_scored")),
        "home_away_goals_conceded": _safe(home_stats.get("away_goals_conceded")),
        "away_home_goals_scored": _safe(away_stats.get("home_goals_scored")),
        "away_home_goals_conceded": _safe(away_stats.get("home_goals_conceded")),
        "away_away_goals_scored": _safe(away_stats.get("away_goals_scored")),
        "away_away_goals_conceded": _safe(away_stats.get("away_goals_conceded")),
        "home_rolling5_xg_for": _safe(home_stats.get("rolling5_xg_for")),
        "home_rolling5_xg_against": _safe(home_stats.get("rolling5_xg_against")),
        "home_rolling10_xg_for": _safe(home_stats.get("rolling10_xg_for")),
        "home_rolling10_xg_against": _safe(home_stats.get("rolling10_xg_against")),
        "away_rolling5_xg_for": _safe(away_stats.get("rolling5_xg_for")),
        "away_rolling5_xg_against": _safe(away_stats.get("rolling5_xg_against")),
        "away_rolling10_xg_for": _safe(away_stats.get("rolling10_xg_for")),
        "away_rolling10_xg_against": _safe(away_stats.get("rolling10_xg_against")),
        "home_form5_wins": _safe(home_stats.get("form5_wins")),
        "home_form5_draws": _safe(home_stats.get("form5_draws")),
        "home_form5_losses": _safe(home_stats.get("form5_losses")),
        "home_form5_points": _safe(home_stats.get("form5_points")),
        "home_form5_avg_points": _safe(home_stats.get("form5_avg_points")),
        "home_form10_wins": _safe(home_stats.get("form10_wins")),
        "home_form10_draws": _safe(home_stats.get("form10_draws")),
        "home_form10_losses": _safe(home_stats.get("form10_losses")),
        "home_form10_points": _safe(home_stats.get("form10_points")),
        "home_form10_avg_points": _safe(home_stats.get("form10_avg_points")),
        "away_form5_wins": _safe(away_stats.get("form5_wins")),
        "away_form5_draws": _safe(away_stats.get("form5_draws")),
        "away_form5_losses": _safe(away_stats.get("form5_losses")),
        "away_form5_points": _safe(away_stats.get("form5_points")),
        "away_form5_avg_points": _safe(away_stats.get("form5_avg_points")),
        "away_form10_wins": _safe(away_stats.get("form10_wins")),
        "away_form10_draws": _safe(away_stats.get("form10_draws")),
        "away_form10_losses": _safe(away_stats.get("form10_losses")),
        "away_form10_points": _safe(away_stats.get("form10_points")),
        "away_form10_avg_points": _safe(away_stats.get("form10_avg_points")),
        "home_matches_played": _safe(home_stats.get("matches_played")),
        "away_matches_played": _safe(away_stats.get("matches_played")),
        "home_points": _safe(home_stats.get("points")),
        "away_points": _safe(away_stats.get("points")),
        "odds_home_close": _safe(market_odds.get("home")),
        "odds_draw_close": _safe(market_odds.get("draw")),
        "odds_away_close": _safe(market_odds.get("away")),
        "odds_over25": _safe(market_odds.get("over25")),
        "odds_under25": _safe(market_odds.get("under25")),
        "odds_btts_yes": _safe(market_odds.get("btts")),
        "odds_btts_no": _safe(market_odds.get("btts_no")),
        "imp_home": _safe(market_odds.get("imp_home")),
        "imp_draw": _safe(market_odds.get("imp_draw")),
        "imp_away": _safe(market_odds.get("imp_away")),
        "imp_over25": _safe(market_odds.get("imp_over25")),
        "imp_under25": _safe(market_odds.get("imp_under25")),
        "imp_btts_yes": _safe(market_odds.get("imp_btts_yes")),
        "imp_btts_no": _safe(market_odds.get("imp_btts_no")),
    }


def predict_1x2_probs(
    home_elo: float,
    away_elo: float,
    home_stats: Optional[Dict],
    away_stats: Optional[Dict],
    market_odds: Optional[Dict],
) -> Optional[Dict[str, float]]:
    model, feature_columns = _load_model()
    if model is None or not feature_columns:
        return None
    try:
        import xgboost as xgb  # type: ignore
        import pandas as pd  # type: ignore

        feature_map = build_feature_vector(home_elo, away_elo, home_stats, away_stats, market_odds)
        row = {name: feature_map.get(name, 0.0) for name in feature_columns}
        dmat = xgb.DMatrix(pd.DataFrame([row]))
        probs = model.predict(dmat)[0]
        # Class map from training_pipeline: 0 away, 1 draw, 2 home
        return {
            "prob_home_win": float(probs[2]),
            "prob_draw": float(probs[1]),
            "prob_away_win": float(probs[0]),
        }
    except Exception:
        return None

