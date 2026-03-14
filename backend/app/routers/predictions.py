from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from typing import Optional
from datetime import datetime, timedelta, timezone
import asyncio
import json
import logging
import re
import time

from app.database import get_db
from app.models.models import Match, Team, Prediction
from app.schemas.schemas import PredictionRequest
from app.services.prediction_engine import predict_match
from app.services.normalization import normalize_team_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])


# Function removed in favor of app.services.normalization.normalize_team_name


async def _resolve_alias_team_ids(db: AsyncSession, base_team_id: int, league_id: Optional[int]) -> set[int]:
    team_row = (await db.execute(select(Team).where(Team.id == base_team_id))).scalar_one_or_none()
    if not team_row:
        return {base_team_id}

    target_key = normalize_team_name(team_row.name)
    q = select(Team)
    if league_id:
        q = q.where(Team.league_id == league_id)
    teams = (await db.execute(q)).scalars().all()
    
    ids = {t.id for t in teams if normalize_team_name(t.name) == target_key}
    ids.add(base_team_id)
    return ids


def _serialize_score_matrix(matrix: Optional[dict]) -> Optional[dict]:
    if matrix is None:
        return None
    return {k: float(v) for k, v in matrix.items()}


@router.post("/generate", response_model=dict)
async def generate_prediction(
    payload: PredictionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a prediction for a specific match."""
    # Fetch the match
    result = await db.execute(
        select(Match).where(Match.id == payload.match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Fetch recent matches for both teams from a wider horizon so early-season
    # fixtures still have meaningful history.
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * 3)

    home_alias_ids = await _resolve_alias_team_ids(db, match.home_team_id, match.league_id)
    away_alias_ids = await _resolve_alias_team_ids(db, match.away_team_id, match.league_id)

    async def get_recent(team_ids: set[int]):
        q = (
            select(Match)
            .where(
                and_(
                    or_(Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)),
                    Match.status == "finished",
                    Match.match_date >= cutoff,
                    Match.id != match.id,
                )
            )
            .order_by(desc(Match.match_date))
            .limit(25)
        )
        r = await db.execute(q)
        rows = r.scalars().all()
        return [
            {
                "home_team_id": m.home_team_id,
                "away_team_id": m.away_team_id,
                "home_goals": m.home_goals or 0,
                "away_goals": m.away_goals or 0,
                "xg_home": m.xg_home or 0,
                "xg_away": m.xg_away or 0,
                "match_date": m.match_date.isoformat() if m.match_date else None,
                "goals_for": m.home_goals if m.home_team_id in team_ids else m.away_goals,
                "goals_against": m.away_goals if m.home_team_id in team_ids else m.home_goals,
            }
            for m in rows
        ]

    home_recent = await get_recent(home_alias_ids)
    away_recent = await get_recent(away_alias_ids)

    # Fetch team Elo ratings
    teams_result = await db.execute(select(Team).where(Team.id.in_([match.home_team_id, match.away_team_id])))
    teams_fetched = teams_result.scalars().all()
    home_team = next((t for t in teams_fetched if t.id == match.home_team_id), None)
    away_team = next((t for t in teams_fetched if t.id == match.away_team_id), None)

    home_elo = home_team.elo_rating if home_team else 1500.0
    away_elo = away_team.elo_rating if away_team else 1500.0
    home_name = home_team.name if home_team else "Home Team"
    away_name = away_team.name if away_team else "Away Team"

    # Build historical results for Dixon-Coles fitting
    all_matches_q = (
        select(Match)
        .where(
            Match.status == "finished",
            Match.league_id == match.league_id,
            Match.match_date >= cutoff,
        )
        .order_by(desc(Match.match_date))
        .limit(200)
    )
    all_r = await db.execute(all_matches_q)
    all_matches = [m for m in all_r.scalars().all()
                   if m.home_goals is not None and m.away_goals is not None]

    # Bulk-load all team names in one query (fixes N+1)
    hist_team_ids = set()
    for m in all_matches:
        hist_team_ids.add(m.home_team_id)
        hist_team_ids.add(m.away_team_id)
    if hist_team_ids:
        team_rows = (await db.execute(
            select(Team).where(Team.id.in_(hist_team_ids))
        )).scalars().all()
        team_name_map = {t.id: t.name for t in team_rows}
    else:
        team_name_map = {}

    historical = []
    for m in all_matches:
        ht_name = team_name_map.get(m.home_team_id)
        at_name = team_name_map.get(m.away_team_id)
        if ht_name and at_name:
            match_dt = m.match_date if m.match_date.tzinfo else m.match_date.replace(tzinfo=timezone.utc)
            days_ago = max(0, (datetime.now(timezone.utc) - match_dt).days)
            historical.append({
                "home_team": ht_name,
                "away_team": at_name,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "days_ago": days_ago,
            })

    # Market odds
    market_odds = None
    if payload.include_betting:
        candidates = {}
        if match.odds_home_close:
            candidates["home"] = match.odds_home_close
        if match.odds_draw_close:
            candidates["draw"] = match.odds_draw_close
        if match.odds_away_close:
            candidates["away"] = match.odds_away_close
        if match.odds_over25:
            candidates["over25"] = match.odds_over25
        if match.odds_under25:
            candidates["under25"] = match.odds_under25
        if match.odds_btts_yes:
            candidates["btts"] = match.odds_btts_yes
        if match.odds_btts_no:
            candidates["btts_no"] = match.odds_btts_no
        if candidates:
            market_odds = candidates

    # Fetch Players & Injuries
    from app.models.models import Player, TeamStats
    
    async def get_players(team_id: int):
        r = await db.execute(select(Player).where(Player.team_id == team_id))
        rows = r.scalars().all()
        return [
            {
                "name": p.name,
                "is_injured": p.is_injured,
                "is_suspended": p.is_suspended,
                "xg_per90": p.xg_per90,
                "xa_per90": p.xa_per90,
                "position": p.position
            }
            for p in rows
        ]
        
    async def get_team_stats(team_id: int):
        r = await db.execute(select(TeamStats).where(TeamStats.team_id == team_id))
        stats = r.scalar_one_or_none()
        if not stats:
            return None
        return {
            "ppda": stats.ppda,
            "xg_for": stats.xg_for,
            "xg_against": stats.xg_against,
            "shots_per_game": stats.shots_per_game
        }

    home_players, away_players = await asyncio.gather(
        get_players(match.home_team_id),
        get_players(match.away_team_id)
    )
    home_stats, away_stats = await asyncio.gather(
        get_team_stats(match.home_team_id),
        get_team_stats(match.away_team_id)
    )

    # Run CPU-intensive prediction in a thread pool to avoid blocking the event loop
    t0 = time.perf_counter()
    logger.info(f"Generating prediction for match {match.id}: {home_name} vs {away_name}")
    try:
        prediction = await asyncio.wait_for(
            asyncio.to_thread(
                predict_match,
                home_team_name=home_name,
                away_team_name=away_name,
                home_recent_matches=home_recent,
                away_recent_matches=away_recent,
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                home_elo=home_elo,
                away_elo=away_elo,
                home_players=home_players,
                away_players=away_players,
                home_stats=home_stats,
                away_stats=away_stats,
                market_odds=market_odds,
                historical_results=historical if len(historical) >= 20 else None,
                model=payload.model,
            ),
            timeout=90,
        )
    except asyncio.TimeoutError:
        logger.error(f"Prediction timed out for match {match.id} after 90s")
        raise HTTPException(
            status_code=504,
            detail="Prediction took too long. Try again — the model may need fewer historical matches.",
        )
    elapsed = time.perf_counter() - t0
    logger.info(f"Prediction for match {match.id} completed in {elapsed:.2f}s")

    # Persist prediction
    existing = await db.execute(select(Prediction).where(Prediction.match_id == match.id))
    pred_obj = existing.scalar_one_or_none()

    score_matrix_json = json.dumps(prediction.get("score_matrix", {}))

    if pred_obj:
        pred_obj.prob_home_win = prediction["prob_home_win"]
        pred_obj.prob_draw = prediction["prob_draw"]
        pred_obj.prob_away_win = prediction["prob_away_win"]
        pred_obj.expected_goals_home = prediction["expected_goals_home"]
        pred_obj.expected_goals_away = prediction["expected_goals_away"]
        pred_obj.expected_goals_total = prediction["expected_goals_total"]
        pred_obj.prob_over25 = prediction["prob_over25"]
        pred_obj.prob_under25 = prediction["prob_under25"]
        pred_obj.prob_btts_yes = prediction["prob_btts_yes"]
        pred_obj.prob_btts_no = prediction["prob_btts_no"]
        pred_obj.score_matrix = score_matrix_json
        pred_obj.confidence = prediction["confidence"]
        pred_obj.model_used = payload.model
    else:
        pred_obj = Prediction(
            match_id=match.id,
            model_used=payload.model,
            prob_home_win=prediction["prob_home_win"],
            prob_draw=prediction["prob_draw"],
            prob_away_win=prediction["prob_away_win"],
            expected_goals_home=prediction["expected_goals_home"],
            expected_goals_away=prediction["expected_goals_away"],
            expected_goals_total=prediction["expected_goals_total"],
            prob_over25=prediction["prob_over25"],
            prob_under25=prediction["prob_under25"],
            prob_btts_yes=prediction["prob_btts_yes"],
            prob_btts_no=prediction["prob_btts_no"],
            score_matrix=score_matrix_json,
            confidence=prediction["confidence"],
        )
        db.add(pred_obj)

    await db.commit()
    prediction["prediction_id"] = pred_obj.id
    return prediction


@router.get("/{prediction_id}")
async def get_prediction(prediction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    data = {c.name: getattr(pred, c.name) for c in pred.__table__.columns}
    if data.get("score_matrix"):
        try:
            data["score_matrix"] = json.loads(data["score_matrix"])
        except Exception:
            pass
    return data


@router.get("/match/{match_id}")
async def get_prediction_for_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prediction).where(Prediction.match_id == match_id))
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="No prediction found for this match")
    data = {c.name: getattr(pred, c.name) for c in pred.__table__.columns}
    if data.get("score_matrix"):
        try:
            data["score_matrix"] = json.loads(data["score_matrix"])
        except Exception:
            pass
    return data


@router.get("/")
async def list_predictions(
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Prediction).order_by(desc(Prediction.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    preds = result.scalars().all()
    out = []
    for pred in preds:
        data = {c.name: getattr(pred, c.name) for c in pred.__table__.columns}
        if data.get("score_matrix"):
            try:
                data["score_matrix"] = json.loads(data["score_matrix"])
            except Exception:
                pass
        out.append(data)
    return out


@router.post("/ai-analysis/{match_id}")
async def ai_match_analysis(match_id: int, model: str = "llama-4-maverick", db: AsyncSession = Depends(get_db)):
    """
    Generate AI-powered analysis combining prediction engine + analysis data.
    Requires a prediction to already exist for this match.
    Accepts optional `model` query param: llama-4-maverick | deepseek-r1 | gpt-oss-120b
    """
    from app.services.ai_analysis import generate_ai_analysis, GROQ_MODELS
    from app.routers.matches import pre_match_analysis

    # 1. Get existing prediction
    pred_result = await db.execute(
        select(Prediction).where(Prediction.match_id == match_id)
    )
    pred = pred_result.scalar_one_or_none()
    if not pred:
        raise HTTPException(
            status_code=400,
            detail="Generate a prediction first before requesting AI analysis"
        )

    pred_data = {c.name: getattr(pred, c.name) for c in pred.__table__.columns}
    if pred_data.get("score_matrix"):
        try:
            pred_data["score_matrix"] = json.loads(pred_data["score_matrix"])
        except Exception:
            pass

    # 2. Get match info
    match_result = await db.execute(
        select(Match).where(Match.id == match_id)
    )
    match = match_result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    teams_res = await db.execute(select(Team).where(Team.id.in_([match.home_team_id, match.away_team_id])))
    teams_fetched_analysis = teams_res.scalars().all()
    home_t = next((t for t in teams_fetched_analysis if t.id == match.home_team_id), None)
    away_t = next((t for t in teams_fetched_analysis if t.id == match.away_team_id), None)

    match_info = {
        "home_team": home_t.name if home_t else "Home",
        "away_team": away_t.name if away_t else "Away",
        "league": "",
    }
    if match.league_id:
        from app.models.models import League
        league_row = (await db.execute(select(League).where(League.id == match.league_id))).scalar_one_or_none()
        if league_row:
            match_info["league"] = league_row.name

    # 3. Try to get pre-match analysis (best effort)
    analysis_data = None
    try:
        analysis_data = await pre_match_analysis(match_id, db)
    except Exception:
        pass

    # 4. Generate AI analysis
    result = await generate_ai_analysis(pred_data, analysis_data, match_info, model=model)
    result["model_used"] = model
    result["model_label"] = GROQ_MODELS.get(model, {}).get("label", model)
    return result


@router.post("/ai-consensus/{match_id}")
async def ai_consensus_analysis(match_id: int, db: AsyncSession = Depends(get_db)):
    """
    Generate consensus AI analysis by running all 3 Groq models in parallel,
    then synthesising their outputs into a single definitive prediction.
    """
    from app.services.ai_analysis import generate_consensus_analysis
    from app.routers.matches import pre_match_analysis

    # 1. Get existing prediction
    pred_result = await db.execute(
        select(Prediction).where(Prediction.match_id == match_id)
    )
    pred = pred_result.scalar_one_or_none()
    if not pred:
        raise HTTPException(
            status_code=400,
            detail="Generate a prediction first before requesting AI consensus"
        )

    pred_data = {c.name: getattr(pred, c.name) for c in pred.__table__.columns}
    if pred_data.get("score_matrix"):
        try:
            pred_data["score_matrix"] = json.loads(pred_data["score_matrix"])
        except Exception:
            pass

    # 2. Get match info
    match_result = await db.execute(
        select(Match).where(Match.id == match_id)
    )
    match = match_result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    teams_res = await db.execute(select(Team).where(Team.id.in_([match.home_team_id, match.away_team_id])))
    teams_list = teams_res.scalars().all()
    home_t = next((t for t in teams_list if t.id == match.home_team_id), None)
    away_t = next((t for t in teams_list if t.id == match.away_team_id), None)

    match_info = {
        "home_team": home_t.name if home_t else "Home",
        "away_team": away_t.name if away_t else "Away",
        "league": "",
    }
    if match.league_id:
        from app.models.models import League
        league_row = (await db.execute(select(League).where(League.id == match.league_id))).scalar_one_or_none()
        if league_row:
            match_info["league"] = league_row.name

    # 3. Try to get pre-match analysis (best effort)
    analysis_data = None
    try:
        analysis_data = await pre_match_analysis(match_id, db)
    except Exception:
        pass

    # 4. Generate consensus AI analysis
    result = await generate_consensus_analysis(pred_data, analysis_data, match_info)
    return result
