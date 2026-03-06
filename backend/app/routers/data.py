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
)
from app.services.form_calculator import calculate_team_form
from app.services.dixon_coles import update_elo_ratings
from app.dependencies import verify_admin_key

router = APIRouter(prefix="/data", tags=["data"])

_scrape_status: dict = {}
_fixture_status: dict = {}


async def _get_or_create_league(db: AsyncSession, name: str) -> League:
    result = await db.execute(select(League).where(League.name == name))
    league = result.scalar_one_or_none()
    if not league:
        league = League(name=name)
        db.add(league)
        await db.flush()
    return league


async def _get_or_create_team(db: AsyncSession, name: str, league_id: int) -> Team:
    def _team_key(value: str) -> str:
        # Normalize naming differences across providers
        v = (value or "").strip().lower()
        v = re.sub(r"[^a-z0-9 ]", "", v)
        v = re.sub(r"\b(fc|cf|ac|afc|sc|sv|fk|ifk|club|de|the)\b", "", v)
        v = re.sub(r"\s+", " ", v).strip()
        alias = {
            # Eredivisie
            "fcutrecht": "utrecht",
            "heraclesalmelo": "heracles",
            "ajaxamsterdam": "ajax",
            "psveindhoven": "psv",
            "azalkmaar": "az",
            "fctwente": "twente",
            # La Liga
            "celta": "celtavigo",
            "celtavigo": "celtavigo",
            "celtadevigo": "celtavigo",
            "realbetis": "betis",
            "realbetisbalompie": "betis",
            "athleticclub": "athleticbilbao",
            "athletic": "athleticbilbao",
            "atleticodemadrid": "atleticomadrid",
            "atletico": "atleticomadrid",
            "atlmadrid": "atleticomadrid",
            "deportivoalaves": "alaves",
            "alaves": "alaves",
            "espanyolbarcelona": "espanyol",
            "rayovallecano": "rayo",
            "realvalladolid": "valladolid",
            "realsociedad": "realsociedad",
            "realsociedaddefutbol": "realsociedad",
            # Premier League
            "manchesterunited": "manutd",
            "manunited": "manutd",
            "manchestercity": "mancity",
            "manchestercity": "mancity",
            "tottenhamhotspur": "tottenham",
            "wolverhamptonwanderers": "wolverhampton",
            "wolves": "wolverhampton",
            "newcastleunited": "newcastle",
            "nottinghamforest": "nottmforest",
            "brightonandhovealbion": "brighton",
            "leicestercity": "leicester",
            "westhamunited": "westham",
            "ipswichtown": "ipswich",
            # Serie A
            "acmilan": "milan",
            "internazionale": "inter",
            "hellas": "hellasverona",
            "hellasveronafc": "hellasverona",
            "verona": "hellasverona",
            # Bundesliga
            "bayernmunich": "bayernmunchen",
            "bayern": "bayernmunchen",
            "bayerleverkusen": "leverkusen",
            "borussiamgladbach": "mgladbach",
            "borussiamonchengladbach": "mgladbach",
            "borussiadortmund": "dortmund",
            "eintrachtfrankfurt": "frankfurt",
            # Ligue 1
            "parissaintgermain": "psg",
            "olympiquemarseille": "marseille",
            "olympiquelyonnais": "lyon",
            "asstienne": "stetienne",
            "saintetienne": "stetienne",
        }
        compact = v.replace(" ", "")
        return alias.get(compact, compact)

    # Always resolve within the same league first.
    result = await db.execute(select(Team).where(Team.name == name, Team.league_id == league_id))
    team = result.scalar_one_or_none()
    if not team:
        norm = _team_key(name)
        league_teams_result = await db.execute(select(Team).where(Team.league_id == league_id))
        for existing in league_teams_result.scalars().all():
            if _team_key(existing.name) == norm:
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
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date >= match_date - timedelta(days=2),
                        Match.match_date <= match_date + timedelta(days=2),
                    )
                )
                existing = existing_q.scalar_one_or_none()

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
                        Match.home_team_id == home.id,
                        Match.away_team_id == away.id,
                        Match.match_date >= match_date - timedelta(days=2),
                        Match.match_date <= match_date + timedelta(days=2),
                    )
                )
                existing_row = existing_q.scalar_one_or_none()
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
                Match.home_team_id == home.id,
                Match.away_team_id == away.id,
                Match.match_date >= match_date - timedelta(days=2),
                Match.match_date <= match_date + timedelta(days=2),
            )
        )
        existing = existing_q.scalar_one_or_none()

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
