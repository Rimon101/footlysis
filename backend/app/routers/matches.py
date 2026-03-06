from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Set, Union
from datetime import datetime, timedelta, timezone
import re

from app.database import get_db
from app.models.models import Match, Team, TeamStats
from app.schemas.schemas import MatchOut, MatchCreate, MatchUpdate


def _with_relations(query):
    return query.options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.league),
    )

router = APIRouter(prefix="/matches", tags=["matches"])


def _canonical_team_key(name: Optional[str]) -> str:
    """Normalize provider-specific team names to a shared comparison key."""
    v = (name or "").strip().lower()
    v = re.sub(r"[^a-z0-9 ]", "", v)
    v = re.sub(r"\b(fc|cf|ac|afc|sc|sv|fk|ifk|club|de|the)\b", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    compact = v.replace(" ", "")
    alias = {
        "celta": "celtavigo",
        "realbetis": "betis",
        "athleticclub": "athleticbilbao",
        "athletic": "athleticbilbao",
        "atleticodemadrid": "atleticomadrid",
        "deportivoalaves": "alaves",
        "espanyolbarcelona": "espanyol",
    }
    return alias.get(compact, compact)


def _as_team_id_set(team_ref: Union[int, Set[int]]) -> Set[int]:
    return team_ref if isinstance(team_ref, set) else {team_ref}


async def _resolve_alias_team_ids(
    db: AsyncSession,
    league_id: Optional[int],
    primary_team_id: int,
) -> Set[int]:
    """Return all team IDs across ALL leagues that normalize to the same canonical team key.
    This ensures cross-competition form data (e.g. UCL + domestic) is combined correctly."""
    team_row = await db.execute(select(Team).where(Team.id == primary_team_id))
    primary = team_row.scalar_one_or_none()
    if not primary:
        return {primary_team_id}

    target_key = _canonical_team_key(primary.name)
    all_teams = await db.execute(select(Team))
    ids = {
        t.id for t in all_teams.scalars().all()
        if _canonical_team_key(t.name) == target_key
    }
    ids.add(primary_team_id)
    return ids


@router.get("/", response_model=List[MatchOut])
async def list_matches(
    league_id: Optional[int] = None,
    season: Optional[str] = None,
    team_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    ids: Optional[str] = Query(None, description="Comma-separated match IDs"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Match).order_by(desc(Match.match_date))

    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if id_list:
            query = query.where(Match.id.in_(id_list))

    if league_id:
        query = query.where(Match.league_id == league_id)
    if season:
        query = query.where(Match.season == season)
    if team_id:
        query = query.where(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
    if status:
        query = query.where(Match.status == status)
    if from_date:
        query = query.where(Match.match_date >= from_date)
    if to_date:
        query = query.where(Match.match_date <= to_date)

    query = _with_relations(query).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/upcoming", response_model=List[MatchOut])
async def upcoming_matches(
    days: int = Query(7, ge=1, le=30),
    league_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=days)
    query = (
        select(Match)
        .where(and_(Match.match_date >= now, Match.match_date <= future, Match.status == "scheduled"))
        .order_by(Match.match_date)
    )
    if league_id:
        query = query.where(Match.league_id == league_id)
    result = await db.execute(_with_relations(query))
    return result.scalars().all()


@router.get("/{match_id}", response_model=MatchOut)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_with_relations(select(Match).where(Match.id == match_id)))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("/", response_model=MatchOut, status_code=201)
async def create_match(payload: MatchCreate, db: AsyncSession = Depends(get_db)):
    match = Match(**payload.model_dump())
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


@router.patch("/{match_id}", response_model=MatchOut)
async def update_match(match_id: int, payload: MatchUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(match, key, val)
    await db.commit()
    await db.refresh(match)
    return match


@router.get("/{match_id}/h2h")
async def head_to_head(match_id: int, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Return last N head-to-head results between the two teams."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    h2h_query = (
        select(Match)
        .where(
            or_(
                and_(
                    Match.home_team_id == match.home_team_id,
                    Match.away_team_id == match.away_team_id,
                ),
                and_(
                    Match.home_team_id == match.away_team_id,
                    Match.away_team_id == match.home_team_id,
                ),
            ),
            Match.status == "finished",
            Match.id != match_id,
        )
        .order_by(desc(Match.match_date))
        .limit(limit)
    )
    h2h_result = await db.execute(h2h_query)
    return h2h_result.scalars().all()


# ──────────────────────────────────────────────────────────────────────────────
# Helper: build a full match detail dict from a Match ORM object
# ──────────────────────────────────────────────────────────────────────────────

def _match_detail(m, team_id: Union[int, Set[int]], team_names: Dict[int, str]) -> dict:
    """Serialise one Match row for the 100-match history list."""
    team_ids = _as_team_id_set(team_id)
    is_home = m.home_team_id in team_ids
    scored = (m.home_goals if is_home else m.away_goals) or 0
    conceded = (m.away_goals if is_home else m.home_goals) or 0
    total = scored + conceded
    result = "W" if scored > conceded else ("D" if scored == conceded else "L")
    return {
        "match_id": m.id,
        "date": m.match_date.isoformat() if m.match_date else None,
        "home_team_id": m.home_team_id,
        "away_team_id": m.away_team_id,
        "home_team": team_names.get(m.home_team_id, f"#{m.home_team_id}"),
        "away_team": team_names.get(m.away_team_id, f"#{m.away_team_id}"),
        "home_goals": m.home_goals,
        "away_goals": m.away_goals,
        "ht_home_goals": m.ht_home_goals,
        "ht_away_goals": m.ht_away_goals,
        "xg_home": m.xg_home,
        "xg_away": m.xg_away,
        "shots_home": m.shots_home,
        "shots_away": m.shots_away,
        "shots_on_target_home": m.shots_on_target_home,
        "shots_on_target_away": m.shots_on_target_away,
        "corners_home": m.corners_home,
        "corners_away": m.corners_away,
        "fouls_home": m.fouls_home,
        "fouls_away": m.fouls_away,
        "yellow_home": m.yellow_home,
        "yellow_away": m.yellow_away,
        "red_home": m.red_home,
        "red_away": m.red_away,
        "odds_home": m.odds_home_open,
        "odds_draw": m.odds_draw_open,
        "odds_away": m.odds_away_open,
        "is_home": is_home,
        "venue": "H" if is_home else "A",
        "result": result,
        "goals_for": scored,
        "goals_against": conceded,
        "total_goals": total,
        "season": m.season,
        "league_id": m.league_id,
    }


def _team_match_record(matches, team_id: Union[int, Set[int]], home_only=False, away_only=False):
    """Compute W/D/L, goals, xG, clean sheets, BTTS from a list of Match ORM objects."""
    w = d = l = gf = ga = cs = btts = 0
    xgf = xga = 0.0
    xg_count = 0
    corners_f = corners_a = shots_f = shots_a = sot_f = sot_a = 0
    fouls_f = fouls_a = yellows_f = yellows_a = reds_f = reds_a = 0
    stat_count = 0
    card_count = 0
    foul_count = 0
    scored_first = 0
    ht_leading = 0
    ht_count = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if home_only and not is_home:
            continue
        if away_only and is_home:
            continue
        scored = (m.home_goals if is_home else m.away_goals) or 0
        conceded = (m.away_goals if is_home else m.home_goals) or 0
        gf += scored
        ga += conceded
        if scored > conceded:
            w += 1
        elif scored == conceded:
            d += 1
        else:
            l += 1
        if conceded == 0:
            cs += 1
        if scored > 0 and conceded > 0:
            btts += 1
        if m.xg_home is not None:
            xgf += m.xg_home if is_home else m.xg_away
            xga += m.xg_away if is_home else m.xg_home
            xg_count += 1
        if m.shots_home is not None:
            shots_f += m.shots_home if is_home else m.shots_away
            shots_a += m.shots_away if is_home else m.shots_home
            sot_f += (m.shots_on_target_home if is_home else m.shots_on_target_away) or 0
            sot_a += (m.shots_on_target_away if is_home else m.shots_on_target_home) or 0
            stat_count += 1
        if m.corners_home is not None:
            corners_f += m.corners_home if is_home else m.corners_away
            corners_a += m.corners_away if is_home else m.corners_home
        if m.fouls_home is not None:
            fouls_f += m.fouls_home if is_home else m.fouls_away
            fouls_a += m.fouls_away if is_home else m.fouls_home
            foul_count += 1
        if m.yellow_home is not None:
            yellows_f += m.yellow_home if is_home else m.yellow_away
            yellows_a += m.yellow_away if is_home else m.yellow_home
            reds_f += (m.red_home if is_home else m.red_away) or 0
            reds_a += (m.red_away if is_home else m.red_home) or 0
            card_count += 1
        # Half-time analysis
        if m.ht_home_goals is not None:
            ht_scored = (m.ht_home_goals if is_home else m.ht_away_goals) or 0
            ht_conceded = (m.ht_away_goals if is_home else m.ht_home_goals) or 0
            ht_count += 1
            if ht_scored > ht_conceded:
                ht_leading += 1
            if ht_scored > 0 and conceded == 0:
                scored_first += 1
            elif scored > 0:
                scored_first += 1  # approximate

    total = w + d + l
    if total == 0:
        return None
    total_goals = gf + ga
    # Over/Under thresholds
    o05 = o15 = o25 = o35 = o45 = 0
    for m in matches:
        is_home = m.home_team_id in team_ids
        if home_only and not is_home:
            continue
        if away_only and is_home:
            continue
        tg = ((m.home_goals or 0) + (m.away_goals or 0))
        if tg > 0:
            o05 += 1
        if tg > 1:
            o15 += 1
        if tg > 2:
            o25 += 1
        if tg > 3:
            o35 += 1
        if tg > 4:
            o45 += 1

    return {
        "played": total,
        "wins": w, "draws": d, "losses": l,
        "points": w * 3 + d,
        "goals_for": gf, "goals_against": ga, "goal_diff": gf - ga,
        "avg_goals_for": round(gf / total, 2),
        "avg_goals_against": round(ga / total, 2),
        "avg_total_goals": round(total_goals / total, 2),
        "clean_sheets": cs,
        "clean_sheet_pct": round(cs / total * 100, 1),
        "btts_count": btts,
        "btts_pct": round(btts / total * 100, 1),
        "over05_pct": round(o05 / total * 100, 1),
        "over15_pct": round(o15 / total * 100, 1),
        "over25_pct": round(o25 / total * 100, 1),
        "over35_pct": round(o35 / total * 100, 1),
        "over45_pct": round(o45 / total * 100, 1),
        "avg_xg_for": round(xgf / xg_count, 2) if xg_count else None,
        "avg_xg_against": round(xga / xg_count, 2) if xg_count else None,
        "avg_shots": round(shots_f / stat_count, 1) if stat_count else None,
        "avg_shots_against": round(shots_a / stat_count, 1) if stat_count else None,
        "avg_sot": round(sot_f / stat_count, 1) if stat_count else None,
        "avg_sot_against": round(sot_a / stat_count, 1) if stat_count else None,
        "avg_corners": round(corners_f / stat_count, 1) if stat_count else None,
        "avg_corners_against": round(corners_a / stat_count, 1) if stat_count else None,
        "total_corners_for": corners_f,
        "total_corners_against": corners_a,
        "avg_fouls": round(fouls_f / foul_count, 1) if foul_count else None,
        "avg_fouls_against": round(fouls_a / foul_count, 1) if foul_count else None,
        "total_yellows": yellows_f,
        "total_reds": reds_f,
        "avg_yellows": round(yellows_f / card_count, 1) if card_count else None,
        "avg_yellows_against": round(yellows_a / card_count, 1) if card_count else None,
        "avg_reds": round(reds_f / card_count, 2) if card_count else None,
        "win_pct": round(w / total * 100, 1),
        "draw_pct": round(d / total * 100, 1),
        "loss_pct": round(l / total * 100, 1),
        "ht_leading_pct": round(ht_leading / ht_count * 100, 1) if ht_count else None,
    }


def _goal_distribution(matches, team_id: Union[int, Set[int]]) -> dict:
    """Calculate goal scoring/conceding patterns."""
    scored_dist = {}  # {0: count, 1: count, 2: count, ...}
    conceded_dist = {}
    total_dist = {}
    first_half_goals = 0
    second_half_goals = 0
    ht_count = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        scored = (m.home_goals if is_home else m.away_goals) or 0
        conceded = (m.away_goals if is_home else m.home_goals) or 0
        total = scored + conceded
        scored_dist[scored] = scored_dist.get(scored, 0) + 1
        conceded_dist[conceded] = conceded_dist.get(conceded, 0) + 1
        total_dist[total] = total_dist.get(total, 0) + 1
        if m.ht_home_goals is not None:
            ht_scored = (m.ht_home_goals if is_home else m.ht_away_goals) or 0
            first_half_goals += ht_scored
            second_half_goals += scored - ht_scored
            ht_count += 1

    n = len(matches) or 1
    return {
        "scored_distribution": {str(k): v for k, v in sorted(scored_dist.items())},
        "conceded_distribution": {str(k): v for k, v in sorted(conceded_dist.items())},
        "total_goals_distribution": {str(k): v for k, v in sorted(total_dist.items())},
        "first_half_goals_pct": round(first_half_goals / (first_half_goals + second_half_goals) * 100, 1) if ht_count and (first_half_goals + second_half_goals) > 0 else None,
        "second_half_goals_pct": round(second_half_goals / (first_half_goals + second_half_goals) * 100, 1) if ht_count and (first_half_goals + second_half_goals) > 0 else None,
    }


def _streaks(matches, team_id: Union[int, Set[int]]) -> dict:
    """Calculate current and best streaks."""
    results = []
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        scored = (m.home_goals if is_home else m.away_goals) or 0
        conceded = (m.away_goals if is_home else m.home_goals) or 0
        results.append("W" if scored > conceded else ("D" if scored == conceded else "L"))

    def _current_streak(results_list, target):
        count = 0
        for r in results_list:
            if r == target:
                count += 1
            else:
                break
        return count

    def _max_streak(results_list, target):
        max_s = cur = 0
        for r in results_list:
            if r == target:
                cur += 1
                max_s = max(max_s, cur)
            else:
                cur = 0
        return max_s

    # Unbeaten / winless
    unbeaten = 0
    for r in results:
        if r != "L":
            unbeaten += 1
        else:
            break

    winless = 0
    for r in results:
        if r != "W":
            winless += 1
        else:
            break

    # Scoring / clean sheet streaks
    scoring = 0
    for m in matches:
        is_home = m.home_team_id in team_ids
        scored = (m.home_goals if is_home else m.away_goals) or 0
        if scored > 0:
            scoring += 1
        else:
            break

    cs_streak = 0
    for m in matches:
        is_home = m.home_team_id in team_ids
        conceded = (m.away_goals if is_home else m.home_goals) or 0
        if conceded == 0:
            cs_streak += 1
        else:
            break

    return {
        "current_win_streak": _current_streak(results, "W"),
        "current_draw_streak": _current_streak(results, "D"),
        "current_loss_streak": _current_streak(results, "L"),
        "current_unbeaten": unbeaten,
        "current_winless": winless,
        "current_scoring": scoring,
        "current_clean_sheet": cs_streak,
        "best_win_streak": _max_streak(results, "W"),
        "best_unbeaten": max(sum(1 for _ in g) for k, g in __import__('itertools').groupby(results, key=lambda x: x != "L") if k) if results else 0,
    }


def _cards_analysis(matches, team_id: Union[int, Set[int]]) -> dict:
    """Detailed cards/discipline breakdown."""
    total_y = total_r = opp_y = opp_r = 0
    match_count = 0
    matches_with_cards = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if m.yellow_home is None:
            continue
        match_count += 1
        y = (m.yellow_home if is_home else m.yellow_away) or 0
        r = (m.red_home if is_home else m.red_away) or 0
        oy = (m.yellow_away if is_home else m.yellow_home) or 0
        ore = (m.red_away if is_home else m.red_home) or 0
        total_y += y
        total_r += r
        opp_y += oy
        opp_r += ore
        if y > 0 or r > 0:
            matches_with_cards += 1

    if match_count == 0:
        return None
    return {
        "total_yellows": total_y,
        "total_reds": total_r,
        "avg_yellows": round(total_y / match_count, 1),
        "avg_reds": round(total_r / match_count, 2),
        "opp_avg_yellows": round(opp_y / match_count, 1),
        "opp_avg_reds": round(opp_r / match_count, 2),
        "total_cards_per_match": round((total_y + total_r + opp_y + opp_r) / match_count, 1),
        "matches_analyzed": match_count,
    }


def _corners_analysis(matches, team_id: Union[int, Set[int]]) -> dict:
    """Detailed corner analysis."""
    total_f = total_a = 0
    match_count = 0
    o85 = o95 = o105 = o115 = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if m.corners_home is None:
            continue
        match_count += 1
        cf = (m.corners_home if is_home else m.corners_away) or 0
        ca = (m.corners_away if is_home else m.corners_home) or 0
        total_f += cf
        total_a += ca
        tc = cf + ca
        if tc > 8:
            o85 += 1
        if tc > 9:
            o95 += 1
        if tc > 10:
            o105 += 1
        if tc > 11:
            o115 += 1

    if match_count == 0:
        return None
    return {
        "avg_for": round(total_f / match_count, 1),
        "avg_against": round(total_a / match_count, 1),
        "avg_total": round((total_f + total_a) / match_count, 1),
        "over_8_5_pct": round(o85 / match_count * 100, 1),
        "over_9_5_pct": round(o95 / match_count * 100, 1),
        "over_10_5_pct": round(o105 / match_count * 100, 1),
        "over_11_5_pct": round(o115 / match_count * 100, 1),
        "matches_analyzed": match_count,
    }


def _shots_analysis(matches, team_id: Union[int, Set[int]]) -> dict:
    """Detailed shooting analysis."""
    total_sf = total_sa = total_sotf = total_sota = 0
    match_count = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if m.shots_home is None:
            continue
        match_count += 1
        total_sf += (m.shots_home if is_home else m.shots_away) or 0
        total_sa += (m.shots_away if is_home else m.shots_home) or 0
        total_sotf += (m.shots_on_target_home if is_home else m.shots_on_target_away) or 0
        total_sota += (m.shots_on_target_away if is_home else m.shots_on_target_home) or 0

    if match_count == 0:
        return None
    return {
        "avg_shots": round(total_sf / match_count, 1),
        "avg_shots_against": round(total_sa / match_count, 1),
        "avg_sot": round(total_sotf / match_count, 1),
        "avg_sot_against": round(total_sota / match_count, 1),
        "shot_accuracy_pct": round(total_sotf / total_sf * 100, 1) if total_sf else 0,
        "opp_shot_accuracy_pct": round(total_sota / total_sa * 100, 1) if total_sa else 0,
        "matches_analyzed": match_count,
    }


def _half_time_analysis(matches, team_id: Union[int, Set[int]]) -> dict:
    """Half-time stats: leading at HT, HT result distribution."""
    ht_w = ht_d = ht_l = 0
    match_count = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if m.ht_home_goals is None:
            continue
        match_count += 1
        ht_scored = (m.ht_home_goals if is_home else m.ht_away_goals) or 0
        ht_conceded = (m.ht_away_goals if is_home else m.ht_home_goals) or 0
        if ht_scored > ht_conceded:
            ht_w += 1
        elif ht_scored == ht_conceded:
            ht_d += 1
        else:
            ht_l += 1

    if match_count == 0:
        return None
    return {
        "ht_wins": ht_w,
        "ht_draws": ht_d,
        "ht_losses": ht_l,
        "ht_win_pct": round(ht_w / match_count * 100, 1),
        "ht_draw_pct": round(ht_d / match_count * 100, 1),
        "ht_loss_pct": round(ht_l / match_count * 100, 1),
        "matches_analyzed": match_count,
    }


def _odds_analysis(matches, team_id: Union[int, Set[int]]) -> dict:
    """Odds/value analysis from historical matches."""
    fav_w = fav_l = dog_w = dog_l = 0
    match_count = 0
    team_ids = _as_team_id_set(team_id)
    for m in matches:
        is_home = m.home_team_id in team_ids
        if m.odds_home_open is None:
            continue
        match_count += 1
        team_odds = m.odds_home_open if is_home else m.odds_away_open
        scored = (m.home_goals if is_home else m.away_goals) or 0
        conceded = (m.away_goals if is_home else m.home_goals) or 0
        won = scored > conceded
        if team_odds and team_odds < 2.0:  # favourite
            if won:
                fav_w += 1
            else:
                fav_l += 1
        elif team_odds and team_odds >= 2.5:  # underdog
            if won:
                dog_w += 1
            else:
                dog_l += 1

    if match_count == 0:
        return None
    return {
        "matches_with_odds": match_count,
        "wins_as_favourite": fav_w,
        "losses_as_favourite": fav_l,
        "fav_win_rate": round(fav_w / (fav_w + fav_l) * 100, 1) if (fav_w + fav_l) else None,
        "wins_as_underdog": dog_w,
        "losses_as_underdog": dog_l,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Build team name lookup from a set of matches
# ──────────────────────────────────────────────────────────────────────────────

async def _build_team_names(db: AsyncSession, team_ids: set) -> Dict[int, str]:
    if not team_ids:
        return {}
    result = await db.execute(select(Team).where(Team.id.in_(team_ids)))
    return {t.id: t.name for t in result.scalars().all()}


@router.get("/{match_id}/pre-match-analysis")
async def pre_match_analysis(match_id: int, db: AsyncSession = Depends(get_db)):
    """
    FBRef-style comprehensive pre-match analysis.
    Returns each team's last 100 matches with every stat category:
    form, H2H, goals, xG, shots, corners, cards, half-time, odds, streaks.
    """
    result = await db.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
        )
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    ht_id = match.home_team_id
    at_id = match.away_team_id
    league_id = match.league_id

    home_team_ids = await _resolve_alias_team_ids(db, league_id, ht_id)
    away_team_ids = await _resolve_alias_team_ids(db, league_id, at_id)

    # Fetch last 100 finished matches for each team
    async def _recent(team_ids: Set[int], limit=100):
        q = select(Match).where(
            or_(Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)),
            Match.status == "finished",
            Match.id != match_id,
        ).order_by(desc(Match.match_date)).limit(limit)
        r = await db.execute(q)
        return r.scalars().all()

    home_recent = await _recent(home_team_ids)
    away_recent = await _recent(away_team_ids)

    # Collect all team IDs for name resolution
    all_team_ids = set()
    for m in home_recent + away_recent:
        all_team_ids.add(m.home_team_id)
        all_team_ids.add(m.away_team_id)
    all_team_ids.add(ht_id)
    all_team_ids.add(at_id)
    team_names = await _build_team_names(db, all_team_ids)

    # Form string
    def _form(matches_list, team_ids: Set[int], n=5):
        form = []
        for m in matches_list[:n]:
            is_h = m.home_team_id in team_ids
            s = (m.home_goals if is_h else m.away_goals) or 0
            c = (m.away_goals if is_h else m.home_goals) or 0
            form.append("W" if s > c else ("D" if s == c else "L"))
        return "".join(form)

    # H2H (last 20)
    h2h_q = select(Match).where(
        or_(
            and_(Match.home_team_id.in_(home_team_ids), Match.away_team_id.in_(away_team_ids)),
            and_(Match.home_team_id.in_(away_team_ids), Match.away_team_id.in_(home_team_ids)),
        ),
        Match.status == "finished",
        Match.id != match_id,
    ).order_by(desc(Match.match_date)).limit(20)
    h2h_result = await db.execute(h2h_q)
    h2h_matches = h2h_result.scalars().all()

    # Add H2H team IDs to name map
    for m in h2h_matches:
        all_team_ids.add(m.home_team_id)
        all_team_ids.add(m.away_team_id)
    if all_team_ids - set(team_names.keys()):
        extra = await _build_team_names(db, all_team_ids - set(team_names.keys()))
        team_names.update(extra)

    # H2H summary
    h2h_hw = h2h_aw = h2h_d = 0
    h2h_goals = 0
    h2h_btts = 0
    h2h_o25 = 0
    for m in h2h_matches:
        hg = m.home_goals or 0
        ag = m.away_goals or 0
        h2h_goals += hg + ag
        if hg > 0 and ag > 0:
            h2h_btts += 1
        if (hg + ag) > 2:
            h2h_o25 += 1
        if (m.home_team_id in home_team_ids and hg > ag) or (m.away_team_id in home_team_ids and ag > hg):
            h2h_hw += 1
        elif hg == ag:
            h2h_d += 1
        else:
            h2h_aw += 1

    h2h_details = [_match_detail(m, home_team_ids, team_names) for m in h2h_matches]

    # Full 100-match history as detailed list
    home_history = [_match_detail(m, home_team_ids, team_names) for m in home_recent]
    away_history = [_match_detail(m, away_team_ids, team_names) for m in away_recent]

    # Team objects
    ht_obj = match.home_team
    at_obj = match.away_team

    # Team stats from DB
    async def _get_stats(team_id):
        r = await db.execute(select(TeamStats).where(TeamStats.team_id == team_id))
        s = r.scalar_one_or_none()
        if not s:
            return None
        return {
            "goals_scored": s.goals_scored,
            "goals_conceded": s.goals_conceded,
            "xg_for": s.xg_for,
            "xg_against": s.xg_against,
            "shots_per_game": s.shots_per_game,
            "shots_on_target_pct": s.shots_on_target_pct,
            "clean_sheet_pct": s.clean_sheet_pct,
            "btts_pct": s.btts_pct,
            "form_last_5": s.form_last_5,
            "form_last_10": s.form_last_10,
            "matches_played": s.matches_played,
            "wins": s.wins,
            "draws": s.draws,
            "losses": s.losses,
            "points": s.points,
        }

    n_h2h = len(h2h_matches) or 1

    return {
        "match_id": match_id,
        "home_team": {"id": ht_id, "name": ht_obj.name if ht_obj else None, "elo": ht_obj.elo_rating if ht_obj else None},
        "away_team": {"id": at_id, "name": at_obj.name if at_obj else None, "elo": at_obj.elo_rating if at_obj else None},
        "league": match.league.name if match.league else None,
        "match_date": match.match_date.isoformat() if match.match_date else None,
        "team_names": team_names,

        # ── Form ──
        "home_form": _form(home_recent, home_team_ids, 5),
        "away_form": _form(away_recent, away_team_ids, 5),
        "home_form_10": _form(home_recent, home_team_ids, 10),
        "away_form_10": _form(away_recent, away_team_ids, 10),
        "home_form_20": _form(home_recent, home_team_ids, 20),
        "away_form_20": _form(away_recent, away_team_ids, 20),

        # ── Overall record ──
        "home_overall": _team_match_record(home_recent, home_team_ids),
        "away_overall": _team_match_record(away_recent, away_team_ids),

        # ── Home/Away splits ──
        "home_at_home": _team_match_record(home_recent, home_team_ids, home_only=True),
        "home_at_away": _team_match_record(home_recent, home_team_ids, away_only=True),
        "away_at_home": _team_match_record(away_recent, away_team_ids, home_only=True),
        "away_at_away": _team_match_record(away_recent, away_team_ids, away_only=True),

        # ── Last 5 / 10 / 20 records ──
        "home_last5": _team_match_record(home_recent[:5], home_team_ids),
        "home_last10": _team_match_record(home_recent[:10], home_team_ids),
        "home_last20": _team_match_record(home_recent[:20], home_team_ids),
        "away_last5": _team_match_record(away_recent[:5], away_team_ids),
        "away_last10": _team_match_record(away_recent[:10], away_team_ids),
        "away_last20": _team_match_record(away_recent[:20], away_team_ids),

        # ── Goal Distribution ──
        "home_goals_dist": _goal_distribution(home_recent, home_team_ids),
        "away_goals_dist": _goal_distribution(away_recent, away_team_ids),

        # ── Streaks ──
        "home_streaks": _streaks(home_recent, home_team_ids),
        "away_streaks": _streaks(away_recent, away_team_ids),

        # ── Cards / Discipline ──
        "home_cards": _cards_analysis(home_recent, home_team_ids),
        "away_cards": _cards_analysis(away_recent, away_team_ids),

        # ── Corners ──
        "home_corners": _corners_analysis(home_recent, home_team_ids),
        "away_corners": _corners_analysis(away_recent, away_team_ids),

        # ── Shots ──
        "home_shots": _shots_analysis(home_recent, home_team_ids),
        "away_shots": _shots_analysis(away_recent, away_team_ids),

        # ── Half-Time ──
        "home_half_time": _half_time_analysis(home_recent, home_team_ids),
        "away_half_time": _half_time_analysis(away_recent, away_team_ids),

        # ── Odds / Value ──
        "home_odds_hist": _odds_analysis(home_recent, home_team_ids),
        "away_odds_hist": _odds_analysis(away_recent, away_team_ids),

        # ── H2H ──
        "h2h_summary": {
            "played": len(h2h_matches),
            "home_wins": h2h_hw,
            "away_wins": h2h_aw,
            "draws": h2h_d,
            "total_goals": h2h_goals,
            "avg_goals": round(h2h_goals / n_h2h, 2),
            "btts_count": h2h_btts,
            "btts_pct": round(h2h_btts / n_h2h * 100, 1),
            "over25_count": h2h_o25,
            "over25_pct": round(h2h_o25 / n_h2h * 100, 1),
        },
        "h2h_matches": h2h_details,

        # ── Full 100-Match History ──
        "home_history": home_history,
        "away_history": away_history,
        "home_history_count": len(home_history),
        "away_history_count": len(away_history),

        # ── Team DB Stats ──
        "home_stats": await _get_stats(ht_id),
        "away_stats": await _get_stats(at_id),
    }
