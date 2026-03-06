from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import Team, TeamStats, Match
from app.schemas.schemas import TeamOut, TeamCreate, TeamStatsOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=List[TeamOut])
async def list_teams(
    league_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Team).order_by(Team.name)
    if league_id:
        query = query.where(Team.league_id == league_id)
    if search:
        query = query.where(Team.name.ilike(f"%{search}%"))
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/stats", response_model=TeamStatsOut)
async def get_team_stats(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TeamStats).where(TeamStats.team_id == team_id))
    stats = result.scalar_one_or_none()
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found for this team")
    return stats


@router.get("/{team_id}/recent")
async def get_recent_matches(
    team_id: int,
    limit: int = Query(10, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Recent finished matches for a team."""
    query = (
        select(Match)
        .where(
            and_(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == "finished",
            )
        )
        .order_by(desc(Match.match_date))
        .limit(limit)
    )
    result = await db.execute(query)
    matches = result.scalars().all()
    out = []
    for m in matches:
        is_home = m.home_team_id == team_id
        scored = m.home_goals if is_home else m.away_goals
        conceded = m.away_goals if is_home else m.home_goals
        res = "W" if (scored or 0) > (conceded or 0) else ("D" if scored == conceded else "L")
        out.append({
            "match_id": m.id,
            "date": m.match_date.isoformat() if m.match_date else None,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "xg_home": m.xg_home,
            "xg_away": m.xg_away,
            "is_home": is_home,
            "goals_for": scored,
            "goals_against": conceded,
            "result": res,
            "league_id": m.league_id,
        })
    return out


@router.post("/", response_model=TeamOut, status_code=201)
async def create_team(payload: TeamCreate, db: AsyncSession = Depends(get_db)):
    team = Team(**payload.model_dump())
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@router.get("/{team_id}/xg-trend")
async def xg_trend(
    team_id: int,
    last_n: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return match-by-match xG for charting."""
    query = (
        select(Match)
        .where(
            and_(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == "finished",
                Match.xg_home.isnot(None),
            )
        )
        .order_by(desc(Match.match_date))
        .limit(last_n)
    )
    result = await db.execute(query)
    matches = result.scalars().all()
    trend = []
    for m in reversed(matches):
        is_home = m.home_team_id == team_id
        xgf = m.xg_home if is_home else m.xg_away
        xga = m.xg_away if is_home else m.xg_home
        trend.append({
            "date": m.match_date.isoformat() if m.match_date else None,
            "xg_for": xgf,
            "xg_against": xga,
            "goals_for": m.home_goals if is_home else m.away_goals,
            "goals_against": m.away_goals if is_home else m.home_goals,
        })
    return trend
