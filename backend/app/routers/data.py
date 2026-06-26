from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncio
import re

from app.database import get_db, AsyncSessionLocal
from app.models.models import Match, Team, League, TeamStats, Player
from app.services.data_scraper import (
    scrape_football_data,
    scrape_understat,
    merge_xg_data,
    scrape_upcoming_fixtures,
    scrape_espn_results,
    scrape_fbref_results,
    scrape_single_match,
    scrape_fbref_player_stats,
    LEAGUE_CODES,
    scrape_international_results,
)
from app.services.form_calculator import calculate_team_form
from app.services.dixon_coles import update_elo_ratings
from app.dependencies import verify_admin_key
from app.services.api_football import scrape_api_football_league
from app.services.normalization import normalize_team_name
from app.data.worldcup_2026 import (
    LEAGUE_NAME as WC_LEAGUE_NAME,
    LEAGUE_COUNTRY,
    LEAGUE_SEASON,
    LEAGUE_LOGO,
    GROUPS as WC_GROUPS,
    COUNTRY_CODE as WC_COUNTRY_CODE,
    get_group_stage_fixtures,
    get_knockout_fixtures,
)

router = APIRouter(prefix="/data", tags=["data"])

_scrape_status: dict = {}
_fixture_status: dict = {}
_api_football_status: dict = {}


async def _get_or_create_league(db: AsyncSession, name: str) -> League:
    result = await db.execute(select(League).where(League.name == name))
    league = result.scalar_one_or_none()
    if not league:
        league = League(name=name)
        db.add(league)
        await db.flush()
    return league


async def _get_or_create_team(db: AsyncSession, name: str, league_id: int) -> Team:
    # Function removed in favor of app.services.normalization.normalize_team_name

    # Always resolve within the same league first.
    result = await db.execute(select(Team).where(Team.name == name, Team.league_id == league_id))
    team = result.scalar_one_or_none()
    if not team:
        norm = normalize_team_name(name)
        league_teams_result = await db.execute(select(Team).where(Team.league_id == league_id))
        for existing in league_teams_result.scalars().all():
            if normalize_team_name(existing.name) == norm:
                team = existing
                break

    if not team:
        team = Team(name=name, league_id=league_id)
        db.add(team)
        await db.flush()
    return team


async def _run_scrape(league: str):
    """Background task: scrape data from free sources and persist to DB."""
    _scrape_status[league] = {"status": "running", "started": datetime.now(timezone.utc).isoformat()}
    try:
        fd_matches, us_matches, espn_matches, fbref_matches = await asyncio.gather(
            scrape_football_data(league),
            scrape_understat(league),
            scrape_espn_results(league),
            scrape_fbref_results(league),
        )
        merged = merge_xg_data(fd_matches, us_matches)

        # Merge ESPN current-season results (avoids duplicates by home+away+date)
        existing_keys = set()
        for m in merged:
            try:
                key = (
                    m["home_team"].lower().replace(" ", ""),
                    m["away_team"].lower().replace(" ", ""),
                    str(m.get("match_date", ""))[:10].replace("-", ""),
                )
                existing_keys.add(key)
            except Exception:
                pass

        espn_added = 0
        for em in espn_matches:
            key = (
                em["home_team"].lower().replace(" ", ""),
                em["away_team"].lower().replace(" ", ""),
                str(em.get("match_date", ""))[:10].replace("-", ""),
            )
            if key not in existing_keys:
                merged.append(em)
                existing_keys.add(key)
                espn_added += 1

        fbref_added = 0
        for fm in fbref_matches:
            key = (
                fm["home_team"].lower().replace(" ", ""),
                fm["away_team"].lower().replace(" ", ""),
                str(fm.get("match_date", ""))[:10].replace("-", ""),
            )
            if key not in existing_keys:
                merged.append(fm)
                existing_keys.add(key)
                fbref_added += 1

        _scrape_status[league]["espn_results_added"] = espn_added
        _scrape_status[league]["fbref_results_added"] = fbref_added
        _scrape_status[league]["matches_fetched"] = len(merged)

        if not merged:
            _scrape_status[league]["status"] = "completed"
            _scrape_status[league]["completed"] = datetime.now(timezone.utc).isoformat()
            return

        async with AsyncSessionLocal() as db:
            league_row = await _get_or_create_league(db, league)

            # Build team cache to avoid repeated queries
            team_cache: dict[str, Team] = {}

            async def get_team(name: str) -> Team:
                if name not in team_cache:
                    team_cache[name] = await _get_or_create_team(db, name, league_row.id)
                return team_cache[name]

            inserted = 0
            updated = 0
            for m in merged:
                if not m.get("home_team") or not m.get("away_team") or not m.get("match_date"):
                    continue

                home = await get_team(m["home_team"])
                away = await get_team(m["away_team"])

                # Parse date
                try:
                    match_date = datetime.fromisoformat(m["match_date"])
                    if match_date.tzinfo is None:
                        match_date = match_date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                # Check for duplicate (same home+away+date)
                existing_q = await db.execute(
                    select(Match).where(
                        Match.league_id == league_row.id,
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date >= match_date - timedelta(days=2),
                        Match.match_date <= match_date + timedelta(days=2),
                    )
                )
                existing = existing_q.scalars().first()

                status = "finished" if m.get("home_goals") is not None else "scheduled"

                if existing:
                    # Update status and scores if match is now finished
                    if status == "finished" and existing.status != "finished":
                        existing.status = "finished"
                        existing.home_goals = m.get("home_goals")
                        existing.away_goals = m.get("away_goals")
                    if m.get("matchday") is not None and existing.matchday is None:
                        existing.matchday = m.get("matchday")
                    if m.get("home_goals") is not None and existing.home_goals is None:
                        existing.home_goals = m["home_goals"]
                        existing.away_goals = m.get("away_goals")
                    # Update half-time scores if available
                    if m.get("ht_home_goals") is not None and existing.ht_home_goals is None:
                        existing.ht_home_goals = m["ht_home_goals"]
                        existing.ht_away_goals = m.get("ht_away_goals")
                    # Update xG and odds if newly available
                    if m.get("xg_home") is not None:
                        existing.xg_home = m["xg_home"]
                        existing.xg_away = m["xg_away"]
                    for field in ("odds_home_open", "odds_draw_open", "odds_away_open",
                                  "odds_over25", "odds_under25"):
                        if m.get(field) is not None:
                            setattr(existing, field, m[field])
                    updated += 1
                else:
                    row = Match(
                        league_id=league_row.id,
                        home_team_id=home.id,
                        away_team_id=away.id,
                        match_date=match_date,
                        season=m.get("season", ""),
                        matchday=m.get("matchday"),
                        status=status,
                        home_goals=m.get("home_goals"),
                        away_goals=m.get("away_goals"),
                        ht_home_goals=m.get("ht_home_goals"),
                        ht_away_goals=m.get("ht_away_goals"),
                        xg_home=m.get("xg_home"),
                        xg_away=m.get("xg_away"),
                        shots_home=m.get("shots_home"),
                        shots_away=m.get("shots_away"),
                        shots_on_target_home=m.get("shots_on_target_home"),
                        shots_on_target_away=m.get("shots_on_target_away"),
                        corners_home=m.get("corners_home"),
                        corners_away=m.get("corners_away"),
                        fouls_home=m.get("fouls_home"),
                        fouls_away=m.get("fouls_away"),
                        yellow_home=m.get("yellow_home"),
                        yellow_away=m.get("yellow_away"),
                        red_home=m.get("red_home"),
                        red_away=m.get("red_away"),
                        odds_home_open=m.get("odds_home_open"),
                        odds_draw_open=m.get("odds_draw_open"),
                        odds_away_open=m.get("odds_away_open"),
                        odds_over25=m.get("odds_over25"),
                        odds_under25=m.get("odds_under25"),
                    )
                    db.add(row)
                    inserted += 1

            await db.commit()

        _scrape_status[league].update({
            "status": "completed",
            "completed": datetime.now(timezone.utc).isoformat(),
            "inserted": inserted,
            "updated": updated,
        })
    except Exception as e:
        _scrape_status[league] = {"status": "error", "error": str(e)}


@router.post("/scrape/{league}", dependencies=[Depends(verify_admin_key)])
async def trigger_scrape(league: str, background_tasks: BackgroundTasks):
    """Trigger data scrape for a league (runs in background)."""
    if league not in LEAGUE_CODES:
        raise HTTPException(status_code=400, detail=f"Unknown league. Available: {list(LEAGUE_CODES.keys())}")
    background_tasks.add_task(_run_scrape, league)
    return {"status": "scrape_started", "league": league}


async def _run_fixture_scrape(league: str):
    """Background task: scrape upcoming fixtures and persist to DB."""
    _fixture_status[league] = {"status": "running", "started": datetime.now(timezone.utc).isoformat()}
    try:
        fixtures = await scrape_upcoming_fixtures(league)
        _fixture_status[league]["fixtures_fetched"] = len(fixtures)

        if not fixtures:
            _fixture_status[league].update({
                "status": "completed",
                "completed": datetime.now(timezone.utc).isoformat(),
                "inserted": 0,
                "skipped": 0,
            })
            return

        async with AsyncSessionLocal() as db:
            league_row = await _get_or_create_league(db, league)
            team_cache: dict[str, Team] = {}

            async def get_team(name: str) -> Team:
                if name not in team_cache:
                    team_cache[name] = await _get_or_create_team(db, name, league_row.id)
                return team_cache[name]

            inserted = 0
            skipped = 0
            for f in fixtures:
                if not f.get("home_team") or not f.get("away_team") or not f.get("match_date"):
                    continue

                home = await get_team(f["home_team"])
                away = await get_team(f["away_team"])

                try:
                    match_date = datetime.fromisoformat(f["match_date"])
                    if match_date.tzinfo is None:
                        match_date = match_date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                # Check for duplicate
                existing_q = await db.execute(
                    select(Match).where(
                        Match.league_id == league_row.id,
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date >= match_date - timedelta(days=2),
                        Match.match_date <= match_date + timedelta(days=2),
                    )
                )
                existing_row = existing_q.scalars().first()
                if existing_row:
                    if f.get("matchday") is not None and existing_row.matchday is None:
                        existing_row.matchday = f.get("matchday")
                    skipped += 1
                    continue

                row = Match(
                    league_id=league_row.id,
                    home_team_id=home.id,
                    away_team_id=away.id,
                    match_date=match_date,
                    season=f.get("season", ""),
                    matchday=f.get("matchday"),
                    status="scheduled",
                    home_goals=None,
                    away_goals=None,
                )
                db.add(row)
                inserted += 1

            await db.commit()

        _fixture_status[league].update({
            "status": "completed",
            "completed": datetime.now(timezone.utc).isoformat(),
            "inserted": inserted,
            "skipped": skipped,
        })
    except Exception as e:
        _fixture_status[league] = {"status": "error", "error": str(e)}


@router.post("/scrape-fixtures/{league}", dependencies=[Depends(verify_admin_key)])
async def trigger_fixture_scrape(league: str, background_tasks: BackgroundTasks):
    """Trigger upcoming-fixtures scrape for a league (runs in background)."""
    if league not in LEAGUE_CODES:
        raise HTTPException(status_code=400, detail=f"Unknown league. Available: {list(LEAGUE_CODES.keys())}")
    background_tasks.add_task(_run_fixture_scrape, league)
    return {"status": "fixture_scrape_started", "league": league}


@router.get("/scrape-status")
async def scrape_status():
    return _scrape_status


@router.get("/fixture-scrape-status")
async def fixture_scrape_status():
    return _fixture_status


@router.get("/api-football-scrape-status")
async def api_football_scrape_status():
    return _api_football_status


async def _run_api_football_scrape(league: str):
    _api_football_status[league] = {"status": "running", "started": datetime.now(timezone.utc).isoformat()}
    try:
        matches = await scrape_api_football_league(league)
        _api_football_status[league]["matches_fetched"] = len(matches)

        if not matches:
            _api_football_status[league].update({
                "status": "completed",
                "completed": datetime.now(timezone.utc).isoformat(),
                "inserted": 0,
                "updated": 0,
            })
            return

        async with AsyncSessionLocal() as db:
            league_row = await _get_or_create_league(db, league)
            team_cache: dict[str, Team] = {}

            async def get_team(name: str) -> Team:
                if name not in team_cache:
                    team_cache[name] = await _get_or_create_team(db, name, league_row.id)
                return team_cache[name]

            inserted = 0
            updated = 0
            scheduled_new = 0
            finished_new = 0
            for m in matches:
                if not m.get("home_team") or not m.get("away_team") or not m.get("match_date"):
                    continue

                home = await get_team(m["home_team"])
                away = await get_team(m["away_team"])

                try:
                    match_date = datetime.fromisoformat(m["match_date"])
                    if match_date.tzinfo is None:
                        match_date = match_date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                existing_q = await db.execute(
                    select(Match).where(
                        Match.league_id == league_row.id,
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date >= match_date - timedelta(days=2),
                        Match.match_date <= match_date + timedelta(days=2),
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    if m.get("home_goals") is not None and existing.home_goals is None:
                        existing.status = "finished"
                        existing.home_goals = m["home_goals"]
                        existing.away_goals = m.get("away_goals")
                        existing.ht_home_goals = m.get("ht_home_goals")
                        existing.ht_away_goals = m.get("ht_away_goals")
                        updated += 1
                    elif m.get("matchday") is not None and existing.matchday is None:
                        existing.matchday = m["matchday"]
                        updated += 1
                else:
                    row = Match(
                        league_id=league_row.id,
                        home_team_id=home.id,
                        away_team_id=away.id,
                        match_date=match_date,
                        season=m.get("season", ""),
                        matchday=m.get("matchday"),
                        status=m.get("status", "scheduled"),
                        home_goals=m.get("home_goals"),
                        away_goals=m.get("away_goals"),
                        ht_home_goals=m.get("ht_home_goals"),
                        ht_away_goals=m.get("ht_away_goals"),
                    )
                    db.add(row)
                    inserted += 1
                    if row.status == "scheduled":
                        scheduled_new += 1
                    elif row.status == "finished":
                        finished_new += 1

            await db.commit()

        _api_football_status[league].update({
            "status": "completed",
            "completed": datetime.now(timezone.utc).isoformat(),
            "inserted": inserted,
            "updated": updated,
            "scheduled_new": scheduled_new,
            "finished_new": finished_new,
        })

        # #region agent log
        try:
            import json as _json, time as _time
            from pathlib import Path as _Path
            log_path = _Path("debug-2b6c5a.log")
            payload = {
                "sessionId": "2b6c5a",
                "runId": "initial",
                "hypothesisId": "H1_H2",
                "location": "backend/app/routers/data.py:_run_api_football_scrape",
                "message": "api_football_persist_summary",
                "data": {
                    "league": league,
                    "matches_fetched": len(matches),
                    "inserted": inserted,
                    "updated": updated,
                    "scheduled_new": scheduled_new,
                    "finished_new": finished_new,
                },
                "timestamp": int(_time.time() * 1000),
            }
            with log_path.open("a", encoding="utf-8") as _f:
                _f.write(_json.dumps(payload) + "\n")
        except Exception:
            pass
        # #endregion agent log
    except Exception as e:
        _api_football_status[league] = {"status": "error", "error": str(e)}


@router.post("/scrape-api-football/{league}", dependencies=[Depends(verify_admin_key)])
async def trigger_api_football_scrape(league: str, background_tasks: BackgroundTasks):
    from app.services.api_football import LEAGUE_MAPPING
    if league not in LEAGUE_MAPPING:
        raise HTTPException(status_code=400, detail=f"Unknown league. Available: {list(LEAGUE_MAPPING.keys())}")
    background_tasks.add_task(_run_api_football_scrape, league)
    return {"status": "api_football_scrape_started", "league": league}


@router.post("/scrape-match/{match_id}", dependencies=[Depends(verify_admin_key)])
async def scrape_match(match_id: int, db: AsyncSession = Depends(get_db)):
    """Scrape detailed data for a single match from all sources."""
    from sqlalchemy.orm import selectinload
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

    league_name = match.league.name if match.league else None
    if not league_name:
        raise HTTPException(status_code=400, detail="Match has no league assigned")

    home_name = match.home_team.name if match.home_team else None
    away_name = match.away_team.name if match.away_team else None
    if not home_name or not away_name:
        raise HTTPException(status_code=400, detail="Match teams not found")

    data = await scrape_single_match(home_name, away_name, match.match_date, league_name)

    if not data:
        return {"status": "no_data", "message": "No detailed data found for this match yet."}

    # Update the match record
    updatable = [
        "home_goals", "away_goals", "ht_home_goals", "ht_away_goals",
        "xg_home", "xg_away",
        "shots_home", "shots_away", "shots_on_target_home", "shots_on_target_away",
        "corners_home", "corners_away", "fouls_home", "fouls_away",
        "yellow_home", "yellow_away", "red_home", "red_away",
        "odds_home_open", "odds_draw_open", "odds_away_open",
        "odds_over25", "odds_under25", "status",
    ]
    updated_fields = []
    for field in updatable:
        if field in data and data[field] is not None:
            setattr(match, field, data[field])
            updated_fields.append(field)

    await db.commit()
    await db.refresh(match)

    return {
        "status": "updated",
        "match_id": match_id,
        "fields_updated": updated_fields,
        "data": data,
    }


@router.get("/available-leagues")
async def available_leagues():
    return [
        {"name": league, "football_data_code": codes[0], "understat_slug": codes[1]}
        for league, codes in LEAGUE_CODES.items()
    ]


@router.post("/recalculate-stats", dependencies=[Depends(verify_admin_key)])
async def recalculate_team_stats(
    team_id: Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """Recalculate rolling stats and form for all teams (or a specific one)."""
    team_query = select(Team)
    if team_id:
        team_query = team_query.where(Team.id == team_id)

    teams_result = await db.execute(team_query)
    teams = teams_result.scalars().all()

    updated = 0
    for team in teams:
        matches_q = select(Match).where(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
            Match.status == "finished",
        ).order_by(Match.match_date)

        m_result = await db.execute(matches_q)
        matches = m_result.scalars().all()

        if not matches:
            continue

        match_dicts = [
            {
                "home_team_id": m.home_team_id,
                "away_team_id": m.away_team_id,
                "home_goals": m.home_goals or 0,
                "away_goals": m.away_goals or 0,
                "xg_home": m.xg_home or 0,
                "xg_away": m.xg_away or 0,
                "match_date": m.match_date,
            }
            for m in matches
        ]

        form = calculate_team_form(match_dicts, team.id)

        # Upsert TeamStats
        stats_q = await db.execute(select(TeamStats).where(TeamStats.team_id == team.id))
        stats = stats_q.scalar_one_or_none()

        if not stats:
            stats = TeamStats(team_id=team.id)
            db.add(stats)

        stats.form_last_5 = form["form_last_5"]
        stats.form_last_10 = form["form_last_10"]
        stats.wins = form["wins"]
        stats.draws = form["draws"]
        stats.losses = form["losses"]
        stats.matches_played = form["matches"]
        stats.rolling5_xg_for = form["rolling5_xg_for"]
        stats.rolling5_xg_against = form["rolling5_xg_against"]
        stats.rolling10_xg_for = form["rolling10_xg_for"]
        stats.rolling10_xg_against = form["rolling10_xg_against"]
        stats.goals_scored = form["goals_per_game"] * form["matches"]
        stats.goals_conceded = form["conceded_per_game"] * form["matches"]
        stats.clean_sheet_pct = form["clean_sheet_pct"]
        stats.btts_pct = form["btts_pct"]
        stats.points = form["wins"] * 3 + form["draws"]

        updated += 1

    await db.commit()
    return {"updated_teams": updated}


@router.post("/recalculate-elo", dependencies=[Depends(verify_admin_key)])
async def recalculate_elo(
    league_id: Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """Replay all historical matches to recalculate Elo ratings."""
    query = select(Match).where(Match.status == "finished", Match.home_goals.isnot(None))
    if league_id:
        query = query.where(Match.league_id == league_id)
    query = query.order_by(Match.match_date)

    result = await db.execute(query)
    matches = result.scalars().all()

    elo_map: dict = {}

    for m in matches:
        home_elo = elo_map.get(m.home_team_id, 1500.0)
        away_elo = elo_map.get(m.away_team_id, 1500.0)

        new_home, new_away = update_elo_ratings(
            home_elo, away_elo, m.home_goals or 0, m.away_goals or 0
        )
        elo_map[m.home_team_id] = new_home
        elo_map[m.away_team_id] = new_away

    # Persist updated Elo ratings
    for team_id, elo in elo_map.items():
        t_result = await db.execute(select(Team).where(Team.id == team_id))
        team = t_result.scalar_one_or_none()
        if team:
            team.elo_rating = elo

    await db.commit()
    return {"teams_updated": len(elo_map), "elo_ratings": elo_map}


@router.post("/enrich-match/{match_id}", dependencies=[Depends(verify_admin_key)])
async def enrich_match_data(match_id: int, db: AsyncSession = Depends(get_db)):
    """
    On-demand enrichment: fetch FBref results for this match's league,
    persist any new rows, and return counts so the frontend knows it can
    reload the analysis.  Designed to be called before pre-match-analysis
    when history is insufficient.
    """
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.league))
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    league_name = match.league.name if match.league else None
    if not league_name:
        raise HTTPException(status_code=400, detail="Match has no league assigned")

    # Scrape FBref results for this league (current + 2 previous seasons)
    fbref_matches = await scrape_fbref_results(league_name, seasons_back=2)

    # Fallback to ESPN if FBRef returns no data or fails
    if not fbref_matches:
        fbref_matches = await scrape_espn_results(league_name)

    if not fbref_matches:
        return {"status": "no_data", "inserted": 0, "updated": 0}

    league_row = await _get_or_create_league(db, league_name)
    team_cache: dict[str, Team] = {}

    async def get_team(name: str) -> Team:
        if name not in team_cache:
            team_cache[name] = await _get_or_create_team(db, name, league_row.id)
        return team_cache[name]

    inserted = 0
    updated = 0
    for m in fbref_matches:
        if not m.get("home_team") or not m.get("away_team") or not m.get("match_date"):
            continue

        home = await get_team(m["home_team"])
        away = await get_team(m["away_team"])

        try:
            match_date = datetime.fromisoformat(m["match_date"])
            if match_date.tzinfo is None:
                match_date = match_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        existing_q = await db.execute(
            select(Match).where(
                Match.league_id == league_row.id,
                Match.home_team_id == home.id,
                Match.away_team_id == away.id,
                Match.match_date >= match_date - timedelta(days=2),
                Match.match_date <= match_date + timedelta(days=2),
            )
        )
        existing = existing_q.scalars().first()

        if existing:
            if m.get("home_goals") is not None and existing.home_goals is None:
                existing.home_goals = m["home_goals"]
                existing.away_goals = m.get("away_goals")
                existing.status = "finished"
                updated += 1
            if m.get("matchday") is not None and existing.matchday is None:
                existing.matchday = m.get("matchday")
        else:
            row = Match(
                league_id=league_row.id,
                home_team_id=home.id,
                away_team_id=away.id,
                match_date=match_date,
                season=m.get("season", ""),
                matchday=m.get("matchday"),
                status="finished" if m.get("home_goals") is not None else "scheduled",
                home_goals=m.get("home_goals"),
                away_goals=m.get("away_goals"),
            )
            db.add(row)
            inserted += 1

    await db.commit()
    return {"status": "enriched", "inserted": inserted, "updated": updated}


_player_scrape_status: dict = {}


@router.post("/scrape-players/{league}")
async def scrape_players(league: str, background_tasks: BackgroundTasks):
    """Scrape player stats from FBref for a league."""
    global _player_scrape_status
    if _player_scrape_status.get("status") == "running":
        return _player_scrape_status
    _player_scrape_status = {"status": "running", "league": league, "inserted": 0, "updated": 0}
    background_tasks.add_task(_run_player_scrape, league)
    return _player_scrape_status


@router.get("/player-scrape-status")
async def player_scrape_status():
    return _player_scrape_status or {"status": "idle"}


async def _run_player_scrape(league: str):
    global _player_scrape_status
    try:
        players = await scrape_fbref_player_stats(league)
        if not players:
            _player_scrape_status = {"status": "completed", "league": league, "inserted": 0, "updated": 0, "message": "No player data found"}
            return

        async with AsyncSessionLocal() as db:
            league_row = await _get_or_create_league(db, league)
            team_cache: dict[str, Team] = {}

            async def get_team(name: str) -> Team:
                if name not in team_cache:
                    team_cache[name] = await _get_or_create_team(db, name, league_row.id)
                return team_cache[name]

            inserted = 0
            updated = 0

            for p in players:
                team_name = p.get("team", "").strip()
                if not team_name:
                    continue

                team = await get_team(team_name)

                # Check if player already exists for this team
                existing_q = await db.execute(
                    select(Player).where(
                        Player.name == p["name"],
                        Player.team_id == team.id,
                    )
                )
                existing = existing_q.scalar_one_or_none()

                if existing:
                    # Update stats
                    existing.position = p.get("position") or existing.position
                    existing.nationality = p.get("nationality") or existing.nationality
                    existing.age = p.get("age") or existing.age
                    existing.matches_played = p.get("matches_played", 0)
                    existing.minutes_played = p.get("minutes_played", 0)
                    existing.goals = p.get("goals", 0)
                    existing.assists = p.get("assists", 0)
                    existing.xg_per90 = p.get("xg_per90") or 0
                    existing.xa_per90 = p.get("xa_per90") or 0
                    existing.goals_per90 = p.get("goals_per90") or 0
                    existing.assists_per90 = p.get("assists_per90") or 0
                    existing.progressive_passes = p.get("progressive_passes") or 0
                    existing.shots_per90 = (p.get("shots") or 0) / max(p.get("minutes_played", 1) / 90, 0.1) if p.get("shots") else 0
                    updated += 1
                else:
                    minutes = p.get("minutes_played", 0) or 0
                    per90_div = max(minutes / 90, 0.1)
                    player = Player(
                        name=p["name"],
                        team_id=team.id,
                        position=p.get("position"),
                        nationality=p.get("nationality"),
                        age=p.get("age"),
                        matches_played=p.get("matches_played", 0),
                        minutes_played=minutes,
                        goals=p.get("goals", 0),
                        assists=p.get("assists", 0),
                        xg_per90=p.get("xg_per90") or 0,
                        xa_per90=p.get("xa_per90") or 0,
                        goals_per90=p.get("goals_per90") or 0,
                        assists_per90=p.get("assists_per90") or 0,
                        progressive_passes=p.get("progressive_passes") or 0,
                        shots_per90=(p.get("shots") or 0) / per90_div if p.get("shots") else 0,
                    )
                    db.add(player)
                    inserted += 1

            await db.commit()
            _player_scrape_status = {
                "status": "completed",
                "league": league,
                "inserted": inserted,
                "updated": updated,
            }
    except Exception as e:
        _player_scrape_status = {"status": "error", "league": league, "message": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# FIFA World Cup 2026 — one-off tournament seed
# ──────────────────────────────────────────────────────────────────────────────

_wc_status: dict = {}


async def _get_or_create_wc_team(db: AsyncSession, name: str, league_id: int) -> Team:
    """Find or create a national team, with a deterministic short_name and country."""
    result = await db.execute(select(Team).where(Team.name == name, Team.league_id == league_id))
    team = result.scalar_one_or_none()
    if team:
        return team

    short = name[:3].upper() if not name.startswith("UEFA") and not name.startswith("African") else "TBD"
    country = name if name not in WC_COUNTRY_CODE else name  # we use team name as country name
    team = Team(
        name=name,
        short_name=short,
        league_id=league_id,
        country=country,
    )
    db.add(team)
    await db.flush()
    return team


async def _seed_world_cup() -> dict:
    """Idempotently insert the World Cup 2026 league, 48 teams, and 104 fixtures."""
    _wc_status["status"] = "running"
    _wc_status["started"] = datetime.now(timezone.utc).isoformat()
    summary = {"league": "created", "teams": 0, "matches": 0, "skipped": 0}
    try:
        async with AsyncSessionLocal() as db:
            # 1. League
            result = await db.execute(select(League).where(League.name == WC_LEAGUE_NAME))
            league = result.scalar_one_or_none()
            if not league:
                league = League(
                    name=WC_LEAGUE_NAME,
                    country=LEAGUE_COUNTRY,
                    season=LEAGUE_SEASON,
                    logo_url=LEAGUE_LOGO,
                )
                db.add(league)
                await db.flush()
                summary["league"] = "created"
            else:
                summary["league"] = "exists"
            league_id = league.id

            # 2. Teams
            team_cache: dict[str, Team] = {}
            for group_letter, teams_in_group in WC_GROUPS.items():
                for team_name in teams_in_group:
                    if team_name in team_cache:
                        continue
                    t = await _get_or_create_wc_team(db, team_name, league_id)
                    team_cache[team_name] = t
                    summary["teams"] += 1

            # 3. Fixtures (group stage + knockout)
            def _to_utc(y, m, d, t):
                local = datetime(y, m, d, *map(int, t.split(":")))
                return (local + timedelta(hours=4)).replace(tzinfo=timezone.utc)

            YEAR = 2026
            all_fixtures = []
            for f in get_group_stage_fixtures():
                all_fixtures.append({
                    "home": f["home_team"],
                    "away": f["away_team"],
                    "match_date": _to_utc(f["year"], f["month"], f["day"], f["time_et"]),
                    "matchday": None,
                    "stage_label": f"Group {f['group']}",
                })
            stage_names = {"R32": "Round of 32", "R16": "Round of 16",
                           "QF": "Quarter-final", "SF": "Semi-final",
                           "3RD": "Third place", "F": "Final"}
            for f in get_knockout_fixtures():
                all_fixtures.append({
                    "home": f["home_label"],
                    "away": f["away_label"],
                    "match_date": _to_utc(YEAR, f["month"], f["day"], f["time_et"]),
                    "matchday": f["match"],
                    "stage_label": stage_names[f["stage"]],
                })

            # Knockout placeholders ("1A", "3B/C/D/E/F", "W97", "L109", …) need
            # stub teams so the row can be inserted.  Each one is created under
            # the World Cup league with a [WC] tag so it can be renamed later.
            # NOTE: must run BEFORE the fixture loop, not after.
            for fx_placeholder in (
                "1A", "1B", "1C", "1D", "1E", "1F", "1G", "1H", "1I", "1J", "1K", "1L",
                "2A", "2B", "2C", "2D", "2E", "2F", "2G", "2H",
                "3A", "3B", "3C", "3D", "3E", "3F", "3H", "3I",
                "3B/C/D/E/F", "3C/D/E/F", "3A/B/F/H/I", "3A/C/D/F", "3B/C/E/F/I",
                "3A/B/C/D", "3A/B/C", "3A/B/C/D", "3D/E/F/I", "3C/D/E/F",
                "3E/F/H/I", "3D/E/H/I", "3A/B/C",
                "W89", "W90", "W91", "W92", "W93", "W94", "W95", "W96",
                "W97", "W98", "W99", "W100", "W101", "W102", "W103", "W104",
                "W105", "W106", "W107", "W108", "W109", "W110",
                "L109", "L110",
            ):
                if fx_placeholder in team_cache:
                    continue
                team_cache[fx_placeholder] = await _get_or_create_wc_team(
                    db, f"[WC] {fx_placeholder}", league_id
                )
                summary["teams"] += 1

            for fx in all_fixtures:
                home = team_cache[fx["home"]]
                away = team_cache[fx["away"]]

                # idempotency: same (league, home, away, date)
                existing_q = await db.execute(
                    select(Match).where(
                        Match.league_id == league_id,
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date == fx["match_date"],
                    )
                )
                if existing_q.scalar_one_or_none():
                    summary["skipped"] += 1
                    continue

                db.add(Match(
                    league_id=league_id,
                    home_team_id=home.id,
                    away_team_id=away.id,
                    match_date=fx["match_date"],
                    season=LEAGUE_SEASON,
                    matchday=fx["matchday"],
                    status="scheduled",
                ))
                summary["matches"] += 1

            await db.commit()
        _wc_status.update({
            "status": "completed",
            "completed": datetime.now(timezone.utc).isoformat(),
            **summary,
        })
        return _wc_status
    except Exception as exc:
        _wc_status.update({"status": "error", "error": str(exc)})
        raise


@router.post("/seed-world-cup", dependencies=[Depends(verify_admin_key)])
async def seed_world_cup(background_tasks: BackgroundTasks):
    """Seed the World Cup 2026 league, teams and fixtures (idempotent)."""
    background_tasks.add_task(_seed_world_cup)
    return {"status": "seed_started"}


@router.get("/world-cup-seed-status")
async def world_cup_seed_status():
    return _wc_status


_nations_scrape_status: dict = {}


async def _run_nations_scrape():
    """Background task: fetch all historical international match results for World Cup 2026 playing nations."""
    _nations_scrape_status["status"] = "running"
    _nations_scrape_status["started"] = datetime.now(timezone.utc).isoformat()
    _nations_scrape_status["message"] = "Downloading historical match dataset..."
    summary = {"league_count": 0, "team_count": 0, "match_count": 0, "skipped_count": 0}
    try:
        # 1. Fetch matches from CSV
        matches_data = await scrape_international_results()
        _nations_scrape_status["message"] = f"Downloaded {len(matches_data)} matching rows. Processing database insertions..."
        
        # 2. Ensure the World Cup 2026 league and teams exist in the database (or seed it)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(League).where(League.name == WC_LEAGUE_NAME))
            wc_league = result.scalar_one_or_none()
            if not wc_league:
                _nations_scrape_status["message"] = "Seeding World Cup 2026 league and team structures first..."
                await _seed_world_cup()
                result = await db.execute(select(League).where(League.name == WC_LEAGUE_NAME))
                wc_league = result.scalar_one_or_none()
            
            wc_league_id = wc_league.id
            
            # Load all existing teams in memory
            team_result = await db.execute(select(Team))
            existing_teams = team_result.scalars().all()
            
            teams_map = {}
            for t in existing_teams:
                norm_name = normalize_team_name(t.name)
                if norm_name not in teams_map or t.league_id == wc_league_id:
                    teams_map[norm_name] = t
            
            # Load all existing leagues in memory
            league_result = await db.execute(select(League))
            existing_leagues = league_result.scalars().all()
            leagues_map = {normalize_team_name(l.name): l for l in existing_leagues}
            
            new_leagues = {}
            new_teams = {}
            
            # Pre-load existing matches in memory to avoid duplicate inserts
            match_result = await db.execute(
                select(Match.home_team_id, Match.away_team_id, Match.match_date)
            )
            existing_match_keys = set()
            for h_id, a_id, m_date in match_result.all():
                if m_date:
                    date_str = m_date.strftime("%Y-%m-%d")
                    existing_match_keys.add((h_id, a_id, date_str))
            
            # Helper to get/create team in memory/db cache
            async def get_or_create_nation_team(name: str) -> Team:
                norm_name = normalize_team_name(name)
                if norm_name in teams_map:
                    return teams_map[norm_name]
                if norm_name in new_teams:
                    return new_teams[norm_name]
                
                short = name[:3].upper()
                t = Team(
                    name=name,
                    short_name=short,
                    league_id=wc_league_id,
                    country=name,
                )
                db.add(t)
                new_teams[norm_name] = t
                summary["team_count"] += 1
                return t
                
            # Helper to get/create league in memory/db cache
            async def get_or_create_tournament_league(name: str) -> League:
                norm_name = normalize_team_name(name)
                if norm_name in leagues_map:
                    return leagues_map[norm_name]
                if norm_name in new_leagues:
                    return new_leagues[norm_name]
                
                l = League(
                    name=name,
                    country="International",
                    season="2026",
                )
                db.add(l)
                new_leagues[norm_name] = l
                summary["league_count"] += 1
                return l

            # Collect unique names
            unique_tournaments = set()
            unique_nations = set()
            for m in matches_data:
                unique_tournaments.add(m["tournament"])
                unique_nations.add(m["home_team"])
                unique_nations.add(m["away_team"])
                
            for l_name in unique_tournaments:
                await get_or_create_tournament_league(l_name)
            
            for t_name in unique_nations:
                await get_or_create_nation_team(t_name)
                
            await db.flush()
            
            # Update mappings
            for norm, l in new_leagues.items():
                leagues_map[norm] = l
            for norm, t in new_teams.items():
                teams_map[norm] = t
                
            # Loop over matches and construct Match objects
            for m in matches_data:
                home_norm = normalize_team_name(m["home_team"])
                away_norm = normalize_team_name(m["away_team"])
                
                home_team = teams_map[home_norm]
                away_team = teams_map[away_norm]
                league_obj = leagues_map[normalize_team_name(m["tournament"])]
                
                date_str = m["date"]
                match_key = (home_team.id, away_team.id, date_str)
                if match_key in existing_match_keys:
                    summary["skipped_count"] += 1
                    continue
                
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                
                home_goals = m["home_score"]
                away_goals = m["away_score"]
                
                season_str = date_str[:4]
                
                match_obj = Match(
                    league_id=league_obj.id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    match_date=dt,
                    season=season_str,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    status="finished",
                )
                db.add(match_obj)
                existing_match_keys.add(match_key)
                summary["match_count"] += 1
            
            _nations_scrape_status["message"] = "Saving matches to database..."
            await db.commit()
            
            # Recalculating ELO ratings chronologically
            _nations_scrape_status["message"] = "Recalculating Elo ratings for all national teams..."
            query = select(Match).where(Match.status == "finished", Match.home_goals.isnot(None))
            query = query.order_by(Match.match_date)
            result = await db.execute(query)
            all_finished = result.scalars().all()
            
            elo_map = {}
            for m in all_finished:
                home_elo = elo_map.get(m.home_team_id, 1500.0)
                away_elo = elo_map.get(m.away_team_id, 1500.0)
                new_home, new_away = update_elo_ratings(
                    home_elo, away_elo, m.home_goals or 0, m.away_goals or 0
                )
                elo_map[m.home_team_id] = new_home
                elo_map[m.away_team_id] = new_away
                
            for team_id, elo in elo_map.items():
                t_row = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
                if t_row:
                    t_row.elo_rating = elo
            
            # Recalculating team stats & forms
            _nations_scrape_status["message"] = "Recalculating team stats and forms..."
            all_teams = (await db.execute(select(Team))).scalars().all()
            for team in all_teams:
                m_q = select(Match).where(
                    (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
                    Match.status == "finished",
                ).order_by(Match.match_date)
                team_matches = (await db.execute(m_q)).scalars().all()
                if not team_matches:
                    continue
                
                match_dicts = [
                    {
                        "home_team_id": tm.home_team_id,
                        "away_team_id": tm.away_team_id,
                        "home_goals": tm.home_goals or 0,
                        "away_goals": tm.away_goals or 0,
                        "xg_home": tm.xg_home or 0,
                        "xg_away": tm.xg_away or 0,
                        "match_date": tm.match_date,
                    }
                    for tm in team_matches
                ]
                form = calculate_team_form(match_dicts, team.id)
                stats_q = await db.execute(select(TeamStats).where(TeamStats.team_id == team.id))
                stats = stats_q.scalar_one_or_none()
                if not stats:
                    stats = TeamStats(team_id=team.id)
                    db.add(stats)
                
                stats.form_last_5 = form["form_last_5"]
                stats.form_last_10 = form["form_last_10"]
                stats.wins = form["wins"]
                stats.draws = form["draws"]
                stats.losses = form["losses"]
                stats.matches_played = form["matches"]
                stats.rolling5_xg_for = form["rolling5_xg_for"]
                stats.rolling5_xg_against = form["rolling5_xg_against"]
                stats.rolling10_xg_for = form["rolling10_xg_for"]
                stats.rolling10_xg_against = form["rolling10_xg_against"]
                stats.goals_scored = form["goals_per_game"] * form["matches"]
                stats.goals_conceded = form["conceded_per_game"] * form["matches"]
                stats.clean_sheet_pct = form["clean_sheet_pct"]
                stats.btts_pct = form["btts_pct"]
                stats.points = form["wins"] * 3 + form["draws"]
            
            await db.commit()
            
        _nations_scrape_status.update({
            "status": "completed",
            "message": "Nations historical scrape and stats calculation finished successfully!",
            "completed": datetime.now(timezone.utc).isoformat(),
            **summary,
        })
    except Exception as exc:
        _nations_scrape_status.update({
            "status": "error",
            "message": f"Error: {str(exc)}",
            "completed": datetime.now(timezone.utc).isoformat(),
        })
        raise exc


@router.post("/scrape-nations", dependencies=[Depends(verify_admin_key)])
async def scrape_nations(background_tasks: BackgroundTasks):
    """Trigger background scraping of historical results for World Cup playing nations."""
    background_tasks.add_task(_run_nations_scrape)
    return {"status": "nations_scrape_started"}


@router.get("/nations-scrape-status")
async def nations_scrape_status():
    return _nations_scrape_status

