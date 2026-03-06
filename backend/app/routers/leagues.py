from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.database import get_db
from app.models.models import League, Team, Match
from app.schemas.schemas import LeagueOut, LeagueCreate

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/", response_model=List[LeagueOut])
async def list_leagues(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(League).order_by(League.name))
    return result.scalars().all()


@router.get("/{league_id}", response_model=LeagueOut)
async def get_league(league_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.post("/", response_model=LeagueOut, status_code=201)
async def create_league(payload: LeagueCreate, db: AsyncSession = Depends(get_db)):
    league = League(**payload.model_dump())
    db.add(league)
    await db.commit()
    await db.refresh(league)
    return league


@router.get("/{league_id}/standings")
async def get_standings(league_id: int, season: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Compute standings from match results."""
    query = select(Match).where(
        Match.league_id == league_id,
        Match.status == "finished",
        Match.home_goals.isnot(None),
    )
    
    if season:
        query = query.where(Match.season == season)
    else:
        # If no season provided, find the most recent season for this league
        latest_season_q = await db.execute(
            select(Match.season)
            .where(Match.league_id == league_id, Match.status == "finished")
            .order_by(Match.match_date.desc())
            .limit(1)
        )
        latest_seasonStr = latest_season_q.scalar_one_or_none()
        if latest_seasonStr:
            query = query.where(Match.season == latest_seasonStr)

    result = await db.execute(query)
    matches = result.scalars().all()

    # Collect all team IDs
    team_ids = set()
    for m in matches:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)

    # Build standings dict
    table = {
        tid: {"team_id": tid, "mp": 0, "w": 0, "d": 0, "l": 0,
              "gf": 0, "ga": 0, "gd": 0, "pts": 0, "cs": 0, "btts": 0}
        for tid in team_ids
    }

    for m in matches:
        hg, ag = m.home_goals or 0, m.away_goals or 0
        h, a = m.home_team_id, m.away_team_id

        table[h]["mp"] += 1
        table[a]["mp"] += 1
        table[h]["gf"] += hg
        table[h]["ga"] += ag
        table[a]["gf"] += ag
        table[a]["ga"] += hg

        if ag == 0:
            table[h]["cs"] += 1
        if hg == 0:
            table[a]["cs"] += 1
        if hg > 0 and ag > 0:
            table[h]["btts"] += 1
            table[a]["btts"] += 1

        if hg > ag:
            table[h]["w"] += 1
            table[h]["pts"] += 3
            table[a]["l"] += 1
        elif hg < ag:
            table[a]["w"] += 1
            table[a]["pts"] += 3
            table[h]["l"] += 1
        else:
            table[h]["d"] += 1
            table[a]["d"] += 1
            table[h]["pts"] += 1
            table[a]["pts"] += 1

    # Fetch team names
    teams_result = await db.execute(select(Team).where(Team.id.in_(list(team_ids))))
    teams_map = {t.id: t.name for t in teams_result.scalars().all()}

    standings = []
    for tid, row in table.items():
        row["gd"] = row["gf"] - row["ga"]
        row["team_name"] = teams_map.get(tid, str(tid))
        row["clean_sheet_pct"] = round(row["cs"] / row["mp"] * 100, 1) if row["mp"] else 0
        row["btts_pct"] = round(row["btts"] / row["mp"] * 100, 1) if row["mp"] else 0
        standings.append(row)

    standings.sort(key=lambda x: (-x["pts"], -x["gd"], -x["gf"]))
    for i, row in enumerate(standings):
        row["position"] = i + 1

    return standings
