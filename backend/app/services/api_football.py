import aiohttp
import asyncio
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# By default point to the direct v3 API, but this might get overridden by RapidAPI host
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

# Mapping between our internal league names and API-Football IDs
LEAGUE_MAPPING = {
    "Premier League": 39,
    "Championship": 40,
    "La Liga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Coupe de France": 66,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Scottish Premiership": 281,
    "Saudi Pro League": 307,
    "UEFA Champions League": 2,
    "UEFA Europa League": 3,
    "UEFA Conference League": 848,
    "Copa del Rey": 143,
    "FA Cup": 45,
    "DFB-Pokal": 81,
    "Coppa Italia": 137,
}

def get_headers_and_base_url() -> tuple[dict, str]:
    # Support both naming conventions for the direct subscription
    direct_key = os.getenv("API_FOOTBALL_KEY") or os.getenv("FOOTBALL_API_KEY")
    # Support RapidAPI
    rapid_key = os.getenv("RAPID_API_KEY")
    rapid_host = os.getenv("RAPID_API_HOST", "api-football-v1.p.rapidapi.com")

    if rapid_key:
        return {
            "x-rapidapi-key": rapid_key,
            "x-rapidapi-host": rapid_host
        }, f"https://{rapid_host}/v3"
        
    if direct_key:
        return {
            "x-apisports-key": direct_key,
        }, "https://v3.football.api-sports.io"
        
    raise ValueError("No API-Football key found. Please set API_FOOTBALL_KEY or RAPID_API_KEY in your .env file.")

async def fetch_api_football_data(session: aiohttp.ClientSession, endpoint: str, params: dict) -> dict:
    """Helper function to make requests to API-Football."""
    headers, base_url = get_headers_and_base_url()
    url = f"{base_url}/{endpoint}"
    
    async with session.get(url, headers=headers, params=params) as response:
        data = await response.json()
        if response.status != 200:
            raise Exception(f"API-Football request failed with status {response.status}: {data}")
        
        if data.get("errors") and len(data["errors"]) > 0:
            raise Exception(f"API-Football returned errors: {data['errors']}")
            
        return data

async def scrape_api_football_league(league_name: str) -> List[Dict]:
    """
    Scrape fixtures and results for a given league for the current season 
    using API-Football v3.
    """
    league_id = LEAGUE_MAPPING.get(league_name)
    if not league_id:
        raise ValueError(f"No API-Football mapping found for league: {league_name}")

    # API-Football requires exactly the year the season starts in
    # e.g., for 2025/2026, the season is "2025"
    now = datetime.now(timezone.utc)
    season_year = now.year if now.month >= 7 else now.year - 1

    season_str = f"{season_year}/{season_year + 1}"

    matches = []
    
    async with aiohttp.ClientSession() as session:
        params = {
            "league": league_id,
            "season": season_year
        }
        data = await fetch_api_football_data(session, "fixtures", params)
        
        for fixture_data in data.get("response", []):
            fixture = fixture_data.get("fixture", {})
            league_info = fixture_data.get("league", {})
            teams = fixture_data.get("teams", {})
            goals = fixture_data.get("goals", {})
            score = fixture_data.get("score", {})

            home_team = teams.get("home", {}).get("name")
            away_team = teams.get("away", {}).get("name")
            match_date_str = fixture.get("date")
            
            if not home_team or not away_team or not match_date_str:
                continue

            try:
                match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            status_short = fixture.get("status", {}).get("short")
            status = "finished" if status_short in ["FT", "AET", "PEN"] else "scheduled"

            home_goals = goals.get("home") if status == "finished" else None
            away_goals = goals.get("away") if status == "finished" else None
            
            ht_home_goals = score.get("halftime", {}).get("home") if status == "finished" else None
            ht_away_goals = score.get("halftime", {}).get("away") if status == "finished" else None

            matchday_raw = league_info.get("round", "")
            matchday = None
            if "Regular Season - " in matchday_raw:
                try:
                    matchday = int(matchday_raw.replace("Regular Season - ", ""))
                except ValueError:
                    pass

            matches.append({
                "league": league_name,
                "season": season_str,
                "matchday": matchday,
                "match_date": match_date.isoformat(),
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "ht_home_goals": ht_home_goals,
                "ht_away_goals": ht_away_goals,
                "status": status,
            })

    return matches
