from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models.models import Player, Team
from app.schemas.schemas import PlayerOut, PlayerCreate

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/", response_model=List[PlayerOut])
async def list_players(
    team_id: Optional[int] = None,
    position: Optional[str] = None,
    injured_only: bool = False,
    suspended_only: bool = False,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Player).options(selectinload(Player.team)).order_by(Player.name)
    if team_id:
        query = query.where(Player.team_id == team_id)
    if position:
        query = query.where(Player.position.ilike(f"%{position}%"))
    if injured_only:
        query = query.where(Player.is_injured == True)
    if suspended_only:
        query = query.where(Player.is_suspended == True)
    if search:
        query = query.where(Player.name.ilike(f"%{search}%"))
    query = query.limit(limit)
    result = await db.execute(query)
    players = result.scalars().all()
    for p in players:
        p.team_name = p.team.name if p.team else None
    return players


@router.get("/unavailable")
async def get_unavailable_players(
    team_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Players who are injured or suspended."""
    query = select(Player).where(
        or_(Player.is_injured == True, Player.is_suspended == True)
    )
    if team_id:
        query = query.where(Player.team_id == team_id)
    result = await db.execute(query)
    players = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "team_id": p.team_id,
            "position": p.position,
            "is_injured": p.is_injured,
            "injury_detail": p.injury_detail,
            "injury_return": p.injury_return.isoformat() if p.injury_return else None,
            "is_suspended": p.is_suspended,
            "suspension_matches": p.suspension_matches,
            "xg_per90": p.xg_per90,
        }
        for p in players
    ]


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(player_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).options(selectinload(Player.team)).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.team_name = player.team.name if player.team else None
    return player


@router.post("/", response_model=PlayerOut, status_code=201)
async def create_player(payload: PlayerCreate, db: AsyncSession = Depends(get_db)):
    player = Player(**payload.model_dump())
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


@router.patch("/{player_id}/availability")
async def update_availability(
    player_id: int,
    is_injured: Optional[bool] = None,
    injury_detail: Optional[str] = None,
    is_suspended: Optional[bool] = None,
    suspension_matches: Optional[int] = None,
    rotation_risk: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if is_injured is not None:
        player.is_injured = is_injured
    if injury_detail is not None:
        player.injury_detail = injury_detail
    if is_suspended is not None:
        player.is_suspended = is_suspended
    if suspension_matches is not None:
        player.suspension_matches = suspension_matches
    if rotation_risk is not None:
        player.rotation_risk = rotation_risk
    await db.commit()
    await db.refresh(player)
    return {"status": "updated", "player_id": player_id}
