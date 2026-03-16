"""
Training pipeline for a data‑driven match prediction model.

This module does two things:
- build_training_dataset(): pull historical matches + team/odds info into a pandas DataFrame
- train_xgboost_model(): fit an XGBoost model on that dataset and save it to disk

It is intentionally standalone and not imported by FastAPI at startup; you run it
manually (e.g. `python -m app.services.training_pipeline`) when you want to
retrain models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncio

import pandas as pd  # type: ignore

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.models import Match, Team, TeamStats


@dataclass
class DatasetConfig:
    min_season: Optional[int] = None   # e.g. 2018
    max_season: Optional[int] = None   # e.g. 2024
    league_ids: Optional[list[int]] = None  # restrict to subset of leagues
    output_path: Path = Path("models/training_dataset.parquet")


async def _fetch_rows(cfg: DatasetConfig) -> list[tuple[Match, Team, Team, Optional[TeamStats], Optional[TeamStats]]]:
    """Load finished matches with joined team + stats info."""
    async with async_session_maker() as session:  # type: AsyncSession
        q = (
            select(Match, Team, Team, TeamStats, TeamStats)
            .join(Team, Match.home_team_id == Team.id)
            .join(TeamStats, Team.id == TeamStats.team_id, isouter=True)
            .join(Team, Match.away_team_id == Team.id)  # type: ignore[no-redef]
            .join(TeamStats, Team.id == TeamStats.team_id, isouter=True)  # type: ignore[no-redef]
            .where(Match.status == "finished")
        )

        if cfg.league_ids:
            q = q.where(Match.league_id.in_(cfg.league_ids))

        if cfg.min_season or cfg.max_season:
            # seasons are stored as strings like "2023/2024" or "2023"
            if cfg.min_season:
                q = q.where(Match.season >= str(cfg.min_season))
            if cfg.max_season:
                q = q.where(Match.season <= str(cfg.max_season))

        result = await session.stream(q)
        rows: list[tuple[Match, Team, Team, Optional[TeamStats], Optional[TeamStats]]] = []
        async for row in result:
            rows.append(row)
        return rows


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
            d["y_1x2"] = 1  # home
        elif match.home_goals < match.away_goals:
            d["y_1x2"] = -1  # away
        else:
            d["y_1x2"] = 0   # draw
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
        }
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
                "home_form_last5": home_stats.form_last_5,
            }
        )
    if away_stats:
        d.update(
            {
                "away_elo": away.elo_rating,
                "away_ppda": away_stats.ppda,
                "away_goals_scored": away_stats.goals_scored,
                "away_goals_conceded": away_stats.goals_conceded,
                "away_xg_for": away_stats.xg_for,
                "away_xg_against": away_stats.xg_against,
                "away_form_last5": away_stats.form_last_5,
            }
        )

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
) -> None:
    """
    Sketch: train an XGBoost model for 1X2 on the generated dataset.

    This assumes:
    - XGBoost is installed (`pip install xgboost`)
    - dataset_path exists (generated by build_training_dataset)
    """
    import xgboost as xgb  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore

    df = pd.read_parquet(dataset_path)

    # Keep only rows with labels
    df = df.dropna(subset=["y_1x2"])

    # Simple feature set to start with
    feature_cols = [
        "home_elo",
        "away_elo",
        "home_goals_scored",
        "home_goals_conceded",
        "away_goals_scored",
        "away_goals_conceded",
        "home_xg_for",
        "home_xg_against",
        "away_xg_for",
        "away_xg_against",
        "odds_home_close",
        "odds_draw_close",
        "odds_away_close",
    ]
    X = df[feature_cols].fillna(0.0)
    y = df["y_1x2"].astype(int)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )  # shuffle=False keeps temporal ordering roughly intact

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
        verbose_eval=25,
    )

    model_output.parent.mkdir(parents=True, exist_ok=True)
    bst.save_model(model_output.as_posix())


if __name__ == "__main__":
    # Example CLI usage:
    #   python -m app.services.training_pipeline  (build dataset + train model)
    cfg = DatasetConfig()
    path = asyncio.run(build_training_dataset(cfg))
    print(f"Saved training dataset to {path}")
    train_xgboost_model(path)
    print("Trained XGBoost model and saved to models/xgb_1x2.json")

