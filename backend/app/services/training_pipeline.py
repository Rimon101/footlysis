"""
Training pipeline for a data-driven match prediction model.

This module does two things:
- build_training_dataset(): pull historical matches + team/odds info into a pandas DataFrame
- train_xgboost_model(): fit an XGBoost model on that dataset and save it to disk

It is intentionally standalone and not imported by FastAPI at startup; you run it
manually (e.g. `python -m app.services.training_pipeline`) when you want to retrain models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
import json
from pathlib import Path
from typing import Optional

import asyncio

import pandas as pd  # type: ignore

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.database import AsyncSessionLocal
from app.models.models import Match, Team, TeamStats


@dataclass
class DatasetConfig:
    min_season: Optional[int] = None   # e.g. 2018
    max_season: Optional[int] = None   # e.g. 2024
    league_ids: Optional[list[int]] = None  # restrict to subset of leagues
    output_path: Path = Path("models/training_dataset.parquet")
    metrics_output: Path = Path("models/xgb_1x2_metrics.json")


async def _fetch_rows(cfg: DatasetConfig) -> list[tuple[Match, Team, Team, Optional[TeamStats], Optional[TeamStats]]]:
    """Load finished matches with joined team + stats info."""
    home_team = aliased(Team)
    away_team = aliased(Team)
    home_stats = aliased(TeamStats)
    away_stats = aliased(TeamStats)

    async with AsyncSessionLocal() as session:
        q = (
            select(Match, home_team, away_team, home_stats, away_stats)
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
            .join(home_stats, home_team.id == home_stats.team_id, isouter=True)
            .join(away_stats, away_team.id == away_stats.team_id, isouter=True)
            .where(
                Match.status == "finished",
                Match.home_goals.is_not(None),
                Match.away_goals.is_not(None),
            )
            .order_by(Match.match_date.asc())
        )

        if cfg.league_ids:
            q = q.where(Match.league_id.in_(cfg.league_ids))

        if cfg.min_season:
            q = q.where(Match.match_date >= f"{cfg.min_season}-01-01")
        if cfg.max_season:
            q = q.where(Match.match_date < f"{cfg.max_season + 1}-01-01")

        result = await session.execute(q)
        return result.all()


def _row_to_dict(
    match: Match,
    home: Team,
    away: Team,
    home_stats: Optional[TeamStats],
    away_stats: Optional[TeamStats],
) -> dict:
    """Flatten one match row into a feature/label dict."""
    md = match.match_date
    ts = md.replace(tzinfo=timezone.utc).timestamp() if md else None

    d: dict = {
        "match_id": match.id,
        "league_id": match.league_id,
        "season": match.season,
        "match_ts": ts,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        # labels
        "y_home_goals": match.home_goals,
        "y_away_goals": match.away_goals,
    }

    if match.home_goals is not None and match.away_goals is not None:
        if match.home_goals > match.away_goals:
            d["y_1x2"] = 2  # home
        elif match.home_goals < match.away_goals:
            d["y_1x2"] = 0  # away
        else:
            d["y_1x2"] = 1   # draw
        total = (match.home_goals or 0) + (match.away_goals or 0)
        d["y_over25"] = 1 if total > 2 else 0
        d["y_btts"] = 1 if (match.home_goals or 0) > 0 and (match.away_goals or 0) > 0 else 0

    # simple odds features (if present)
    d.update(
        {
            "odds_home_close": match.odds_home_close,
            "odds_draw_close": match.odds_draw_close,
            "odds_away_close": match.odds_away_close,
            "odds_over25": match.odds_over25,
            "odds_btts_yes": match.odds_btts_yes,
            "odds_under25": match.odds_under25,
            "odds_btts_no": match.odds_btts_no,
        }
    )

    def _encode_form(form: Optional[str], prefix: str) -> dict:
        wins = draws = losses = 0
        if form:
            for ch in form.upper():
                if ch == "W":
                    wins += 1
                elif ch == "D":
                    draws += 1
                elif ch == "L":
                    losses += 1
        total = wins + draws + losses
        points = wins * 3 + draws
        avg_points = points / total if total else 0.0
        return {
            f"{prefix}_form_wins": wins,
            f"{prefix}_form_draws": draws,
            f"{prefix}_form_losses": losses,
            f"{prefix}_form_points": points,
            f"{prefix}_form_avg_points": avg_points,
        }

    def _implied_probs_1x2(odds_home: Optional[float], odds_draw: Optional[float], odds_away: Optional[float]) -> dict:
        try:
            if not odds_home or not odds_draw or not odds_away:
                return {"imp_home": 0.0, "imp_draw": 0.0, "imp_away": 0.0}
            inv_h = 1.0 / odds_home
            inv_d = 1.0 / odds_draw
            inv_a = 1.0 / odds_away
            total = inv_h + inv_d + inv_a
            if total <= 0:
                return {"imp_home": 0.0, "imp_draw": 0.0, "imp_away": 0.0}
            return {"imp_home": inv_h / total, "imp_draw": inv_d / total, "imp_away": inv_a / total}
        except Exception:
            return {"imp_home": 0.0, "imp_draw": 0.0, "imp_away": 0.0}

    def _implied_probs_pair(odds_a: Optional[float], odds_b: Optional[float], a_key: str, b_key: str) -> dict:
        try:
            if not odds_a or not odds_b:
                return {a_key: 0.0, b_key: 0.0}
            inv_a = 1.0 / odds_a
            inv_b = 1.0 / odds_b
            total = inv_a + inv_b
            if total <= 0:
                return {a_key: 0.0, b_key: 0.0}
            return {a_key: inv_a / total, b_key: inv_b / total}
        except Exception:
            return {a_key: 0.0, b_key: 0.0}

    d.update(
        _implied_probs_1x2(match.odds_home_close, match.odds_draw_close, match.odds_away_close)
    )
    d.update(
        _implied_probs_pair(match.odds_over25, match.odds_under25, "imp_over25", "imp_under25")
    )
    d.update(
        _implied_probs_pair(match.odds_btts_yes, match.odds_btts_no, "imp_btts_yes", "imp_btts_no")
    )

    # team‑level season stats snapshots
    if home_stats:
        d.update(
            {
                "home_elo": home.elo_rating,
                "home_ppda": home_stats.ppda,
                "home_goals_scored": home_stats.goals_scored,
                "home_goals_conceded": home_stats.goals_conceded,
                "home_xg_for": home_stats.xg_for,
                "home_xg_against": home_stats.xg_against,
                "home_shots_per_game": home_stats.shots_per_game,
                "home_shots_on_target_pct": home_stats.shots_on_target_pct,
                "home_big_chances_created": home_stats.big_chances_created,
                "home_shot_conversion_rate": home_stats.shot_conversion_rate,
                "home_clean_sheet_pct": home_stats.clean_sheet_pct,
                "home_btts_pct": home_stats.btts_pct,
                "home_home_goals_scored": home_stats.home_goals_scored,
                "home_home_goals_conceded": home_stats.home_goals_conceded,
                "home_away_goals_scored": home_stats.away_goals_scored,
                "home_away_goals_conceded": home_stats.away_goals_conceded,
                "home_rolling5_xg_for": home_stats.rolling5_xg_for,
                "home_rolling5_xg_against": home_stats.rolling5_xg_against,
                "home_rolling10_xg_for": home_stats.rolling10_xg_for,
                "home_rolling10_xg_against": home_stats.rolling10_xg_against,
                "home_matches_played": home_stats.matches_played,
                "home_points": home_stats.points,
            }
        )
        d.update(_encode_form(home_stats.form_last_5, "home_form5"))
        d.update(_encode_form(home_stats.form_last_10, "home_form10"))
    if away_stats:
        d.update(
            {
                "away_elo": away.elo_rating,
                "away_ppda": away_stats.ppda,
                "away_goals_scored": away_stats.goals_scored,
                "away_goals_conceded": away_stats.goals_conceded,
                "away_xg_for": away_stats.xg_for,
                "away_xg_against": away_stats.xg_against,
                "away_shots_per_game": away_stats.shots_per_game,
                "away_shots_on_target_pct": away_stats.shots_on_target_pct,
                "away_big_chances_created": away_stats.big_chances_created,
                "away_shot_conversion_rate": away_stats.shot_conversion_rate,
                "away_clean_sheet_pct": away_stats.clean_sheet_pct,
                "away_btts_pct": away_stats.btts_pct,
                "away_home_goals_scored": away_stats.home_goals_scored,
                "away_home_goals_conceded": away_stats.home_goals_conceded,
                "away_away_goals_scored": away_stats.away_goals_scored,
                "away_away_goals_conceded": away_stats.away_goals_conceded,
                "away_rolling5_xg_for": away_stats.rolling5_xg_for,
                "away_rolling5_xg_against": away_stats.rolling5_xg_against,
                "away_rolling10_xg_for": away_stats.rolling10_xg_for,
                "away_rolling10_xg_against": away_stats.rolling10_xg_against,
                "away_matches_played": away_stats.matches_played,
                "away_points": away_stats.points,
            }
        )
        d.update(_encode_form(away_stats.form_last_5, "away_form5"))
        d.update(_encode_form(away_stats.form_last_10, "away_form10"))

    return d


async def build_training_dataset(cfg: Optional[DatasetConfig] = None) -> Path:
    """Pull matches + stats into a Parquet file suitable for model training."""
    cfg = cfg or DatasetConfig()
    rows = await _fetch_rows(cfg)
    data = [_row_to_dict(*row) for row in rows]
    df = pd.DataFrame(data)

    cfg.output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cfg.output_path, index=False)
    return cfg.output_path


def train_xgboost_model(
    dataset_path: Path = Path("models/training_dataset.parquet"),
    model_output: Path = Path("models/xgb_1x2.json"),
    metrics_output: Path = Path("models/xgb_1x2_metrics.json"),
) -> None:
    """
    Sketch: train an XGBoost model for 1X2 on the generated dataset.

    This assumes:
    - XGBoost is installed (`pip install xgboost`)
    - dataset_path exists (generated by build_training_dataset)
    """
    import xgboost as xgb  # type: ignore
    from sklearn.metrics import log_loss, accuracy_score  # type: ignore

    df = pd.read_parquet(dataset_path)

    # Keep only rows with labels
    df = df.dropna(subset=["y_1x2"])

    # Simple feature set to start with
    feature_cols = [
        "home_elo",
        "away_elo",
        "home_ppda",
        "away_ppda",
        "home_goals_scored",
        "home_goals_conceded",
        "away_goals_scored",
        "away_goals_conceded",
        "home_xg_for",
        "home_xg_against",
        "away_xg_for",
        "away_xg_against",
        "home_shots_per_game",
        "home_shots_on_target_pct",
        "home_big_chances_created",
        "home_shot_conversion_rate",
        "home_clean_sheet_pct",
        "home_btts_pct",
        "away_shots_per_game",
        "away_shots_on_target_pct",
        "away_big_chances_created",
        "away_shot_conversion_rate",
        "away_clean_sheet_pct",
        "away_btts_pct",
        "home_home_goals_scored",
        "home_home_goals_conceded",
        "home_away_goals_scored",
        "home_away_goals_conceded",
        "away_home_goals_scored",
        "away_home_goals_conceded",
        "away_away_goals_scored",
        "away_away_goals_conceded",
        "home_rolling5_xg_for",
        "home_rolling5_xg_against",
        "home_rolling10_xg_for",
        "home_rolling10_xg_against",
        "away_rolling5_xg_for",
        "away_rolling5_xg_against",
        "away_rolling10_xg_for",
        "away_rolling10_xg_against",
        "home_form5_wins",
        "home_form5_draws",
        "home_form5_losses",
        "home_form5_points",
        "home_form5_avg_points",
        "home_form10_wins",
        "home_form10_draws",
        "home_form10_losses",
        "home_form10_points",
        "home_form10_avg_points",
        "away_form5_wins",
        "away_form5_draws",
        "away_form5_losses",
        "away_form5_points",
        "away_form5_avg_points",
        "away_form10_wins",
        "away_form10_draws",
        "away_form10_losses",
        "away_form10_points",
        "away_form10_avg_points",
        "home_matches_played",
        "away_matches_played",
        "home_points",
        "away_points",
        "odds_home_close",
        "odds_draw_close",
        "odds_away_close",
        "odds_over25",
        "odds_under25",
        "odds_btts_yes",
        "odds_btts_no",
        "imp_home",
        "imp_draw",
        "imp_away",
        "imp_over25",
        "imp_under25",
        "imp_btts_yes",
        "imp_btts_no",
    ]
    X = df[feature_cols].fillna(0.0)
    y = df["y_1x2"].astype(int)

    # Time split (no random shuffle): first 80% train, last 20% validation
    split_idx = max(1, int(len(df) * 0.8))
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval = xgb.DMatrix(X_val, label=y_val)

    params = {
        "objective": "multi:softprob",
        "num_class": 3,
        "eval_metric": "mlogloss",
        "eta": 0.05,
        "max_depth": 4,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
    }

    bst = xgb.train(
        params,
        dtrain,
        num_boost_round=300,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=30,
        verbose_eval=25,
    )

    model_output.parent.mkdir(parents=True, exist_ok=True)
    bst.save_model(model_output.as_posix())
    feature_meta = model_output.with_suffix(".features.json")
    feature_meta.write_text(json.dumps({"feature_columns": feature_cols}, indent=2), encoding="utf-8")

    # Metrics report for quick model-quality tracking
    y_pred_proba = bst.predict(dval)
    y_pred = y_pred_proba.argmax(axis=1)
    report = {
        "rows_total": int(len(df)),
        "rows_train": int(len(X_train)),
        "rows_val": int(len(X_val)),
        "accuracy": float(accuracy_score(y_val, y_pred)) if len(X_val) else None,
        "log_loss": float(log_loss(y_val, y_pred_proba, labels=[0, 1, 2])) if len(X_val) else None,
        "classes": {"away_win": 0, "draw": 1, "home_win": 2},
    }
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    # Example CLI usage:
    #   python -m app.services.training_pipeline  (build dataset + train model)
    cfg = DatasetConfig()
    path = asyncio.run(build_training_dataset(cfg))
    print(f"Saved training dataset to {path}")
    train_xgboost_model(path, metrics_output=cfg.metrics_output)
    print("Trained XGBoost model and saved to models/xgb_1x2.json")

