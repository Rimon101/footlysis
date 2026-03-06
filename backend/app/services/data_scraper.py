"""
Data scraper for free football data sources:
- Football-Data.co.uk (CSV)
- Understat (JSON API embedded in HTML)
- FBRef (upcoming fixture schedules)
"""

import asyncio
import aiohttp
import csv
import json
import re
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from bs4.element import Comment


FOOTBALL_DATA_BASE = "https://www.football-data.co.uk/mmz4281"
UNDERSTAT_BASE = "https://understat.com"
FBREF_BASE = "https://fbref.com/en/comps"
FBREF_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}
FBREF_MIN_REQUEST_INTERVAL_SECONDS = 4.0

LEAGUE_CODES = {
    "Premier League":           ("E0", "EPL"),
    "Championship":             ("E1", None),
    "La Liga":                  ("SP1", "La_liga"),
    "Bundesliga":               ("D1", "Bundesliga"),
    "Serie A":                  ("I1", "Serie_A"),
    "Ligue 1":                  ("F1", "Ligue_1"),
    "Coupe de France":          (None, None),
    "Eredivisie":               ("N1", None),
    "Primeira Liga":            ("P1", None),
    "Scottish Premiership":     ("SC0", None),
    "Saudi Pro League":         (None, None),
    # European competitions
    "UEFA Champions League":    (None, None),
    "UEFA Europa League":       (None, None),
    "UEFA Conference League":   (None, None),
    # Domestic cups
    "Copa del Rey":             (None, None),
    "FA Cup":                   (None, None),
    "DFB-Pokal":                (None, None),
    "Coppa Italia":             (None, None),
}

# FBRef competition IDs + URL slugs
FBREF_COMP = {
    "Premier League":       (9,  "Premier-League"),
    "La Liga":              (12, "La-Liga"),
    "Bundesliga":           (20, "Bundesliga"),
    "Serie A":              (11, "Serie-A"),
    "Ligue 1":              (13, "Ligue-1"),
    "Coupe de France":      (65, "Coupe-de-France"),
    "Championship":         (10, "Championship"),
    "Eredivisie":           (23, "Eredivisie"),
    "Primeira Liga":        (32, "Primeira-Liga"),
    "Scottish Premiership": (40, "Scottish-Premiership"),
    "Saudi Pro League":     (70, "Saudi-Professional-League"),
}

SEASONS = ["2122", "2223", "2324", "2425", "2526"]

_fbref_request_lock = asyncio.Lock()
_last_fbref_request_ts: float = 0.0


# ─── Football-Data.co.uk ──────────────────────────────────────────────────────

def _int(row: dict, col: str) -> Optional[int]:
    v = row.get(col, "")
    try:
        return int(float(v)) if v not in ("", "NA", "N/A", None) else None
    except (ValueError, TypeError):
        return None


def _float(row: dict, col: str) -> Optional[float]:
    v = row.get(col, "")
    try:
        return float(v) if v not in ("", "NA", "N/A", None) else None
    except (ValueError, TypeError):
        return None


async def fetch_football_data_csv(session: aiohttp.ClientSession, season: str, code: str) -> Optional[List[dict]]:
    """Fetch CSV match data from football-data.co.uk"""
    url = f"{FOOTBALL_DATA_BASE}/{season}/{code}.csv"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return None
            text = await resp.text(encoding="latin-1")
            rows = list(csv.DictReader(text.splitlines()))
            return rows
    except Exception:
        return None


def parse_football_data_row(row: dict, league: str, season: str) -> Optional[Dict]:
    """Parse a single CSV row from football-data.co.uk into a match dict."""
    try:
        date_str = row.get("Date", "")
        try:
            match_date = datetime.strptime(date_str, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                match_date = datetime.strptime(date_str, "%d/%m/%y").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        return {
            "league": league,
            "season": season,
            "match_date": match_date.isoformat(),
            "home_team": row.get("HomeTeam", ""),
            "away_team": row.get("AwayTeam", ""),
            "home_goals": _int(row, "FTHG"),
            "away_goals": _int(row, "FTAG"),
            "ht_home_goals": _int(row, "HTHG"),
            "ht_away_goals": _int(row, "HTAG"),
            "shots_home": _int(row, "HS"),
            "shots_away": _int(row, "AS"),
            "shots_on_target_home": _int(row, "HST"),
            "shots_on_target_away": _int(row, "AST"),
            "corners_home": _int(row, "HC"),
            "corners_away": _int(row, "AC"),
            "fouls_home": _int(row, "HF"),
            "fouls_away": _int(row, "AF"),
            "yellow_home": _int(row, "HY"),
            "yellow_away": _int(row, "AY"),
            "red_home": _int(row, "HR"),
            "red_away": _int(row, "AR"),
            "odds_home_open": _float(row, "B365H"),
            "odds_draw_open": _float(row, "B365D"),
            "odds_away_open": _float(row, "B365A"),
            "odds_over25": _float(row, "B365>2.5"),
            "odds_under25": _float(row, "B365<2.5"),
        }
    except Exception:
        return None


async def scrape_football_data(league: str) -> List[Dict]:
    """Scrape all seasons for a given league from football-data.co.uk"""
    code = LEAGUE_CODES.get(league, (None,))[0]
    if not code:
        return []

    matches = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_football_data_csv(session, s, code) for s in SEASONS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for season, rows in zip(SEASONS, results):
            if isinstance(rows, list) and rows:
                for row in rows:
                    m = parse_football_data_row(row, league, f"20{season[:2]}/{season[2:]}")
                    if m and m["home_team"] and m["away_team"]:
                        matches.append(m)

    return matches


# ─── Understat xG Scraper ─────────────────────────────────────────────────────

async def fetch_understat_league(session: aiohttp.ClientSession, league_slug: str, year: int) -> List[Dict]:
    """
    Fetch xG data from Understat for a specific league/season.
    Understat embeds JSON data in page HTML.
    """
    url = f"{UNDERSTAT_BASE}/league/{league_slug}/{year}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()

        # Extract embedded JSON
        match = re.search(r"datesData\s*=\s*JSON\.parse\('(.+?)'\)", html)
        if not match:
            return []

        raw = match.group(1)
        raw = raw.encode().decode("unicode_escape")
        data = json.loads(raw)

        xg_matches = []
        for m in data:
            try:
                xg_matches.append({
                    "understat_id": m.get("id"),
                    "home_team": m.get("h", {}).get("title"),
                    "away_team": m.get("a", {}).get("title"),
                    "home_goals": int(m.get("goals", {}).get("h", 0)),
                    "away_goals": int(m.get("goals", {}).get("a", 0)),
                    "xg_home": float(m.get("xG", {}).get("h", 0)),
                    "xg_away": float(m.get("xG", {}).get("a", 0)),
                    "match_date": m.get("datetime"),
                    "season": str(year),
                    "is_result": m.get("isResult", False),
                })
            except Exception:
                continue
        return xg_matches
    except Exception:
        return []


async def scrape_understat(league: str, years: Optional[List[int]] = None) -> List[Dict]:
    """Scrape xG data for a league across multiple seasons."""
    slug = LEAGUE_CODES.get(league, (None, None))[1]
    if not slug:
        return []

    if not years:
        years = [2021, 2022, 2023, 2024]

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_understat_league(session, slug, y) for y in years]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_matches = []
    for r in results:
        if isinstance(r, list):
            all_matches.extend(r)
    return all_matches


# ─── Injury/Availability Reporter ─────────────────────────────────────────────

async def scrape_injuries_bbc(team_name: str) -> List[Dict]:
    """
    Placeholder for injury data scraping.
    In production, integrate Transfermarkt or a paid injury API.
    Returns empty list if unavailable.
    """
    return []


# ─── Merge xG into Football-Data Matches ─────────────────────────────────────

def merge_xg_data(fd_matches: List[Dict], understat_matches: List[Dict]) -> List[Dict]:
    """
    Merge xG from Understat into football-data matches by home/away team and approximate date.
    """
    # Known cross-source aliases between football-data and Understat naming.
    team_alias = {
        "manchesterunited": "manutd",
        "manchestercity": "mancity",
        "tottenham": "tottenhamhotspur",
        "wolverhamptonwanderers": "wolverhampton",
        "newcastleunited": "newcastleunited",
        "nottinghamforest": "nottinghamforest",
        "brighton": "brighton",
        "brightonandhovealbion": "brighton",
        "westbrom": "westbromwichalbion",
        "qpr": "queensparkrangers",
        "psg": "parissaintgermain",
        "inter": "inter",
        "acmilan": "milan",
    }

    def _norm_team(name: Optional[str]) -> str:
        if not name:
            return ""
        normalized = re.sub(r"[^a-z0-9]", "", str(name).lower())
        return team_alias.get(normalized, normalized)

    def _date_key(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        s = str(value)
        try:
            # Handles both "YYYY-MM-DD" and full ISO timestamps.
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%Y%m%d")
        except Exception:
            raw = s[:10].replace("-", "")
            return raw if len(raw) == 8 and raw.isdigit() else None

    # Build lookup: (home_team_normalized, away_team_normalized, date_yyyymmdd) -> xg
    lookup: Dict[tuple, tuple] = {}
    for m in understat_matches:
        if m.get("home_team") and m.get("away_team") and m.get("match_date"):
            date_key = _date_key(m.get("match_date"))
            if not date_key:
                continue
            key = (
                _norm_team(m.get("home_team")),
                _norm_team(m.get("away_team")),
                date_key,
            )
            lookup[key] = (m.get("xg_home"), m.get("xg_away"))

    for m in fd_matches:
        try:
            base_date = _date_key(m.get("match_date"))
            if not base_date:
                continue

            home_key = _norm_team(m.get("home_team"))
            away_key = _norm_team(m.get("away_team"))

            # Try exact date first; then +/- 1 day to handle timezone drift between sources.
            candidate_dates = [base_date]
            try:
                dt = datetime.strptime(base_date, "%Y%m%d")
                candidate_dates.extend([
                    (dt - timedelta(days=1)).strftime("%Y%m%d"),
                    (dt + timedelta(days=1)).strftime("%Y%m%d"),
                ])
            except Exception:
                pass

            matched = False
            for d in candidate_dates:
                key = (home_key, away_key, d)
                if key in lookup:
                    m["xg_home"], m["xg_away"] = lookup[key]
                    matched = True
                    break

            # Last chance: reversed home/away sometimes appears in bad source rows.
            if not matched:
                for d in candidate_dates:
                    rev_key = (away_key, home_key, d)
                    if rev_key in lookup:
                        xg_h, xg_a = lookup[rev_key]
                        m["xg_home"], m["xg_away"] = xg_a, xg_h
                        break
        except Exception:
            continue

    return fd_matches


# ─── ESPN Results Scraper (current season) ────────────────────────────────────

# ESPN API league slugs (free, no API key required)
ESPN_LEAGUE_SLUGS = {
    "Premier League":           "eng.1",
    "Championship":             "eng.2",
    "La Liga":                  "esp.1",
    "Bundesliga":               "ger.1",
    "Serie A":                  "ita.1",
    "Ligue 1":                  "fra.1",
    "Coupe de France":          "fra.coupe_de_france",
    "Eredivisie":               "ned.1",
    "Primeira Liga":            "por.1",
    "Scottish Premiership":     "sco.1",
    "Saudi Pro League":         "ksa.1",
    # European competitions
    "UEFA Champions League":    "UEFA.CHAMPIONS",
    "UEFA Europa League":       "UEFA.EUROPA",
    "UEFA Conference League":   "UEFA.EUROPA_CONF",
    # Domestic cups
    "Copa del Rey":             "esp.copa_del_rey",
    "FA Cup":                   "eng.fa",
    "DFB-Pokal":                "ger.dfb_pokal",
    "Coppa Italia":             "ita.coppa_italia",
}


async def _fetch_espn_results_chunk(
    session: aiohttp.ClientSession,
    espn_slug: str,
    date_from: str,
    date_to: str,
) -> List[Dict]:
    """Fetch finished matches from ESPN for a date range (YYYYMMDD-YYYYMMDD)."""
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
        f"{espn_slug}/scoreboard?dates={date_from}-{date_to}&limit=100"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []
            return (await resp.json()).get("events", [])
    except Exception:
        return []


async def scrape_espn_results(league: str) -> List[Dict]:
    """
    Scrape current-season finished match results from ESPN's free API.
    Splits the season into monthly chunks to avoid the 100-event limit.
    """
    espn_slug = ESPN_LEAGUE_SLUGS.get(league)
    if not espn_slug:
        return []

    now = datetime.now(timezone.utc)
    season_start_year = now.year if now.month >= 8 else now.year - 1
    season_str = f"{season_start_year}/{season_start_year + 1}"

    # Build monthly date ranges from season start to today
    from datetime import timedelta
    chunks: List[tuple] = []
    cursor = datetime(season_start_year, 8, 1, tzinfo=timezone.utc)
    while cursor < now:
        chunk_end = min(
            datetime(cursor.year, cursor.month + 1, 1, tzinfo=timezone.utc) if cursor.month < 12
            else datetime(cursor.year + 1, 1, 1, tzinfo=timezone.utc),
            now,
        )
        chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end

    matches: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_espn_results_chunk(session, espn_slug, d_from, d_to)
            for d_from, d_to in chunks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for chunk_events in results:
        if not isinstance(chunk_events, list):
            continue
        for event in chunk_events:
            try:
                completed = event.get("status", {}).get("type", {}).get("completed", False)
                if not completed:
                    continue

                match_date_str = event.get("date", "")
                if not match_date_str:
                    continue
                match_date = datetime.fromisoformat(
                    match_date_str.replace("Z", "+00:00")
                )

                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                comp = competitions[0]
                matchday = comp.get("week", {}).get("number")

                home_team = away_team = None
                home_goals = away_goals = None

                for competitor in comp.get("competitors", []):
                    team_name = competitor.get("team", {}).get("displayName", "")
                    score = competitor.get("score", "")
                    try:
                        goals = int(score) if score else None
                    except (ValueError, TypeError):
                        goals = None

                    if competitor.get("homeAway") == "home":
                        home_team = team_name
                        home_goals = goals
                    else:
                        away_team = team_name
                        away_goals = goals

                if not home_team or not away_team:
                    continue

                matches.append({
                    "league": league,
                    "season": season_str,
                    "matchday": int(matchday) if isinstance(matchday, (int, float, str)) and str(matchday).isdigit() else None,
                    "match_date": match_date.isoformat(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "status": "finished",
                })
            except Exception:
                continue

    # Deduplicate
    seen = set()
    unique: List[Dict] = []
    for m in matches:
        key = (
            m["home_team"].lower().replace(" ", ""),
            m["away_team"].lower().replace(" ", ""),
            str(m["match_date"])[:10].replace("-", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


# ─── Upcoming Fixtures Scrapers ───────────────────────────────────────────────

async def _fetch_espn_fixtures(league: str, days_ahead: int = 30) -> List[Dict]:
    """
    Fetch upcoming fixtures from ESPN's free public API.
    Works without API keys and returns structured JSON.
    """
    espn_slug = ESPN_LEAGUE_SLUGS.get(league)
    if not espn_slug:
        return []

    now = datetime.now(timezone.utc)
    season_year = now.year if now.month >= 8 else now.year - 1
    season_str = f"{season_year}/{season_year + 1}"

    fixtures: List[Dict] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        # Build date range string: YYYYMMDD-YYYYMMDD
        from datetime import timedelta
        end_date = now + timedelta(days=days_ahead)
        date_range = f"{now.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"

        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{espn_slug}/scoreboard?dates={date_range}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        for event in data.get("events", []):
            try:
                status_name = event.get("status", {}).get("type", {}).get("name", "")
                # Only include scheduled / not-yet-played matches
                if status_name not in ("STATUS_SCHEDULED", "STATUS_TIMED"):
                    # Also accept if status indicates it hasn't started
                    completed = event.get("status", {}).get("type", {}).get("completed", False)
                    if completed:
                        continue

                match_date_str = event.get("date", "")
                if not match_date_str:
                    continue

                # Parse ISO date from ESPN (e.g. "2026-03-03T19:30Z")
                match_date_str = match_date_str.replace("Z", "+00:00")
                match_date = datetime.fromisoformat(match_date_str)

                # Extract teams from competitions
                competitions = event.get("competitions", [])
                if not competitions:
                    continue

                comp = competitions[0]
                matchday = comp.get("week", {}).get("number")
                home_team = None
                away_team = None

                for competitor in comp.get("competitors", []):
                    team_name = competitor.get("team", {}).get("displayName", "")
                    if competitor.get("homeAway") == "home":
                        home_team = team_name
                    else:
                        away_team = team_name

                if not home_team or not away_team:
                    continue

                fixtures.append({
                    "league": league,
                    "season": season_str,
                    "matchday": int(matchday) if isinstance(matchday, (int, float, str)) and str(matchday).isdigit() else None,
                    "match_date": match_date.isoformat(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_goals": None,
                    "away_goals": None,
                    "status": "scheduled",
                })
            except Exception:
                continue

    except Exception:
        pass

    return fixtures


async def _fbref_get_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch a FBref HTML page with conservative global rate limiting."""
    global _last_fbref_request_ts
    async with _fbref_request_lock:
        now_ts = time.monotonic()
        wait_for = FBREF_MIN_REQUEST_INTERVAL_SECONDS - (now_ts - _last_fbref_request_ts)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _last_fbref_request_ts = time.monotonic()

    try:
        async with session.get(url, headers=FBREF_REQUEST_HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return None
            return await resp.text()
    except Exception:
        return None


def _extract_fbref_schedule_tables(html: str) -> List[BeautifulSoup]:
    """Extract schedule tables from FBref, including tables wrapped in HTML comments."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.select("table[id*='sched']")
    if tables:
        return tables

    # FBref frequently wraps data tables in HTML comments.
    out = []
    for comment in soup.find_all(string=lambda txt: isinstance(txt, Comment)):
        fragment = BeautifulSoup(str(comment), "lxml")
        out.extend(fragment.select("table[id*='sched']"))
    return out


def _parse_fbref_date(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Final fallback for ISO-like strings with time.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_fbref_score(raw: str) -> Optional[tuple[int, int]]:
    """Parse FBref score text into (home_goals, away_goals)."""
    score_text = (raw or "").strip()
    if not score_text:
        return None

    # Handles formats like "2-1", "2-1 (4-3)" and variants with unicode dashes.
    score_text = score_text.replace("–", "-").replace("—", "-")
    direct = re.match(r"^\s*(\d+)\s*-\s*(\d+)", score_text)
    if direct:
        return int(direct.group(1)), int(direct.group(2))

    digits = re.findall(r"\d+", score_text)
    if len(digits) >= 2:
        return int(digits[0]), int(digits[1])
    return None


def _parse_fbref_season_table(table, league: str, now: datetime) -> List[Dict]:
    """Extract finished results from a single FBref schedule table."""
    matches: List[Dict] = []
    tbody = table.find("tbody")
    if not tbody:
        return matches

    for row in tbody.find_all("tr"):
        if "thead" in (row.get("class") or []):
            continue

        date_cell = row.find(attrs={"data-stat": "date"})
        home_cell = row.find(attrs={"data-stat": "home_team"})
        away_cell = row.find(attrs={"data-stat": "away_team"})
        score_cell = row.find(attrs={"data-stat": "score"})
        round_cell = row.find(attrs={"data-stat": "gameweek"})

        raw_date = date_cell.get_text(strip=True) if date_cell else ""
        home_team = home_cell.get_text(strip=True) if home_cell else ""
        away_team = away_cell.get_text(strip=True) if away_cell else ""
        score = score_cell.get_text(strip=True) if score_cell else ""

        if not raw_date or not home_team or not away_team or not score:
            continue

        match_date = _parse_fbref_date(raw_date)
        score_tuple = _parse_fbref_score(score)
        if not match_date or not score_tuple:
            continue

        # Only take matches that have already been played
        if match_date > now:
            continue

        matchday = None
        if round_cell:
            round_text = round_cell.get_text(strip=True)
            digits = re.findall(r"\d+", round_text)
            if digits:
                matchday = int(digits[0])

        home_goals, away_goals = score_tuple
        season_year = match_date.year if match_date.month >= 8 else match_date.year - 1
        season_str = f"{season_year}/{season_year + 1}"

        matches.append({
            "league": league,
            "season": season_str,
            "matchday": matchday,
            "match_date": match_date.isoformat(),
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "status": "finished",
        })

    return matches


# Previous season IDs on FBref (season start year -> FBref season path segment)
# These are used to construct URLs like /en/comps/12/2023-2024/schedule/...
FBREF_PREV_SEASONS = {
    2024: "2024-2025",
    2023: "2023-2024",
    2022: "2022-2023",
    2021: "2021-2022",
}


async def scrape_fbref_results(league: str, seasons_back: int = 2) -> List[Dict]:
    """
    Scrape finished results from FBref schedule pages.
    Fetches the current season plus `seasons_back` previous seasons.
    """
    comp = FBREF_COMP.get(league)
    if not comp:
        return []

    comp_id, slug = comp
    now = datetime.now(timezone.utc)

    # Build list of URLs to fetch (current season + previous seasons)
    urls: List[str] = []
    # Current season (no season path segment needed)
    urls.append(f"{FBREF_BASE}/{comp_id}/schedule/{slug}-Scores-and-Fixtures")
    # Previous seasons
    current_season_start = now.year if now.month >= 8 else now.year - 1
    for i in range(1, seasons_back + 1):
        prev_year = current_season_start - i
        seg = FBREF_PREV_SEASONS.get(prev_year)
        if seg:
            urls.append(
                f"{FBREF_BASE}/{comp_id}/{seg}/schedule/{seg}-{slug}-Scores-and-Fixtures"
            )

    all_matches: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            html = await _fbref_get_html(session, url)
            if not html:
                continue
            for table in _extract_fbref_schedule_tables(html):
                all_matches.extend(_parse_fbref_season_table(table, league, now))

    # Deduplicate by (home, away, yyyymmdd)
    seen = set()
    unique: List[Dict] = []
    for m in all_matches:
        key = (
            m["home_team"].lower().replace(" ", ""),
            m["away_team"].lower().replace(" ", ""),
            str(m["match_date"])[:10].replace("-", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


async def scrape_fbref_upcoming_fixtures(league: str, days_ahead: int = 30) -> List[Dict]:
    """Scrape upcoming fixtures from FBref schedule page for a given league."""
    comp = FBREF_COMP.get(league)
    if not comp:
        return []

    comp_id, slug = comp
    url = f"{FBREF_BASE}/{comp_id}/schedule/{slug}-Scores-and-Fixtures"

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days_ahead)
    season_year = now.year if now.month >= 8 else now.year - 1
    season_str = f"{season_year}/{season_year + 1}"

    async with aiohttp.ClientSession() as session:
        html = await _fbref_get_html(session, url)

    if not html:
        return []

    fixtures: List[Dict] = []
    for table in _extract_fbref_schedule_tables(html):
        tbody = table.find("tbody")
        if not tbody:
            continue

        for row in tbody.find_all("tr"):
            if "thead" in (row.get("class") or []):
                continue

            date_cell = row.find(attrs={"data-stat": "date"})
            home_cell = row.find(attrs={"data-stat": "home_team"})
            away_cell = row.find(attrs={"data-stat": "away_team"})
            score_cell = row.find(attrs={"data-stat": "score"})
            round_cell = row.find(attrs={"data-stat": "gameweek"})

            raw_date = date_cell.get_text(strip=True) if date_cell else ""
            home_team = home_cell.get_text(strip=True) if home_cell else ""
            away_team = away_cell.get_text(strip=True) if away_cell else ""
            score = score_cell.get_text(strip=True) if score_cell else ""

            if not raw_date or not home_team or not away_team:
                continue

            match_date = _parse_fbref_date(raw_date)
            if not match_date:
                continue

            # Keep only upcoming fixtures in the requested window and not already scored.
            if not (now <= match_date <= horizon):
                continue
            if score:
                continue

            matchday = None
            if round_cell:
                round_text = round_cell.get_text(strip=True)
                digits = re.findall(r"\d+", round_text)
                if digits:
                    matchday = int(digits[0])

            fixtures.append({
                "league": league,
                "season": season_str,
                "matchday": matchday,
                "match_date": match_date.isoformat(),
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": None,
                "away_goals": None,
                "status": "scheduled",
            })

    return fixtures


# ─── FBref Player Stats ───────────────────────────────────────────────────────


def _extract_fbref_stats_table(html: str, table_id_fragment: str = "stats_standard") -> Optional[BeautifulSoup]:
    """Extract a stats table from FBref, handling comment-wrapped tables."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=lambda x: x and table_id_fragment in x)
    if table:
        return table

    for comment in soup.find_all(string=lambda txt: isinstance(txt, Comment)):
        if table_id_fragment in str(comment):
            fragment = BeautifulSoup(str(comment), "lxml")
            table = fragment.find("table", id=lambda x: x and table_id_fragment in x)
            if table:
                return table
    return None


def _safe_float(val: str) -> Optional[float]:
    try:
        return float(val.strip()) if val and val.strip() else None
    except (ValueError, AttributeError):
        return None


def _safe_int(val: str) -> Optional[int]:
    try:
        return int(val.strip()) if val and val.strip() else None
    except (ValueError, AttributeError):
        return None


def _get_stat(row, stat_name: str) -> str:
    cell = row.find(attrs={"data-stat": stat_name})
    return cell.get_text(strip=True) if cell else ""


async def scrape_fbref_player_stats(league: str) -> List[Dict]:
    """
    Scrape player standard stats from FBref for the current season.
    Returns a list of dicts with player name, team, position, age, and stats.
    URL: /en/comps/{comp_id}/stats/{slug}-Stats
    """
    comp = FBREF_COMP.get(league)
    if not comp:
        return []

    comp_id, slug = comp
    url = f"{FBREF_BASE}/{comp_id}/stats/{slug}-Stats"

    async with aiohttp.ClientSession() as session:
        html = await _fbref_get_html(session, url)

    if not html:
        return []

    table = _extract_fbref_stats_table(html, "stats_standard")
    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    players: List[Dict] = []
    seen = set()

    for row in tbody.find_all("tr"):
        if "thead" in (row.get("class") or []):
            continue

        name = _get_stat(row, "player")
        if not name or name in seen:
            continue
        seen.add(name)

        team = _get_stat(row, "team")
        position = _get_stat(row, "position")
        nationality_cell = row.find(attrs={"data-stat": "nationality"})
        nationality = ""
        if nationality_cell:
            # FBref often has flag + text, get the text
            a_tag = nationality_cell.find("a")
            if a_tag:
                nationality = a_tag.get_text(strip=True)
            else:
                nationality = nationality_cell.get_text(strip=True)
            # Often format is "xx ENG" => take last part
            parts = nationality.split()
            if parts:
                nationality = parts[-1]

        age_raw = _get_stat(row, "age")
        age = None
        if age_raw:
            # FBref age format: "25-123" (years-days)
            age_parts = age_raw.split("-")
            age = _safe_int(age_parts[0])

        minutes_raw = _get_stat(row, "minutes")
        # Remove commas from numbers like "1,234"
        minutes = _safe_int(minutes_raw.replace(",", "")) if minutes_raw else None

        mp = _safe_int(_get_stat(row, "games"))
        goals = _safe_int(_get_stat(row, "goals"))
        assists = _safe_int(_get_stat(row, "assists"))

        # Per-90 stats
        goals_per90 = _safe_float(_get_stat(row, "goals_per90"))
        assists_per90 = _safe_float(_get_stat(row, "assists_per90"))
        xg = _safe_float(_get_stat(row, "xg"))
        xg_per90 = _safe_float(_get_stat(row, "xg_per90"))
        xa = _safe_float(_get_stat(row, "xg_assist"))
        xa_per90 = _safe_float(_get_stat(row, "xg_assist_per90"))
        progressive_passes = _safe_float(_get_stat(row, "progressive_passes"))

        # Additional
        shots = _safe_float(_get_stat(row, "shots"))
        shots_on_target = _safe_float(_get_stat(row, "shots_on_target"))
        yellow = _safe_int(_get_stat(row, "cards_yellow"))
        red = _safe_int(_get_stat(row, "cards_red"))

        players.append({
            "name": name,
            "team": team,
            "position": position,
            "nationality": nationality,
            "age": age,
            "matches_played": mp or 0,
            "minutes_played": minutes or 0,
            "goals": goals or 0,
            "assists": assists or 0,
            "xg": xg,
            "xa": xa,
            "xg_per90": xg_per90,
            "xa_per90": xa_per90,
            "goals_per90": goals_per90,
            "assists_per90": assists_per90,
            "progressive_passes": progressive_passes,
            "shots": shots,
            "shots_on_target": shots_on_target,
            "yellow_cards": yellow or 0,
            "red_cards": red or 0,
            "league": league,
        })

    return players


async def scrape_upcoming_fixtures(league: str) -> List[Dict]:
    """
    Fetch upcoming fixtures using ESPN plus FBref as a fallback/complementary source.
    Returns deduplicated list of upcoming matches for the given league.
    """
    espn_fixtures, fbref_fixtures = await asyncio.gather(
        _fetch_espn_fixtures(league, days_ahead=30),
        scrape_fbref_upcoming_fixtures(league, days_ahead=30),
        return_exceptions=False,
    )
    fixtures = [*espn_fixtures, *fbref_fixtures]

    # Deduplicate by (home_normalized, away_normalized, date_yyyymmdd)
    seen = set()
    unique: List[Dict] = []
    for f in fixtures:
        key = (
            f["home_team"].lower().replace(" ", ""),
            f["away_team"].lower().replace(" ", ""),
            str(f["match_date"])[:10].replace("-", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


# ─── Single Match Scraper ─────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Normalize team name for comparison."""
    return name.lower().replace(" ", "").replace("fc", "").replace(".", "")


async def scrape_single_match(
    home_team: str, away_team: str, match_date: datetime, league: str
) -> Dict:
    """
    Scrape detailed data for a single match from all available sources.
    Returns a dict with every field that was found.
    """
    result: Dict = {}
    date_key = match_date.strftime("%Y%m%d")
    h_norm = _normalize(home_team)
    a_norm = _normalize(away_team)

    async def _find_in_list(matches: List[Dict]) -> Optional[Dict]:
        for m in matches:
            mh = _normalize(m.get("home_team", ""))
            ma = _normalize(m.get("away_team", ""))
            md = str(m.get("match_date", ""))[:10].replace("-", "")
            if md == date_key and (
                (h_norm in mh or mh in h_norm) and (a_norm in ma or ma in a_norm)
            ):
                return m
        return None

    # 1) Football-Data.co.uk – has shots, corners, cards, odds
    fd_code = LEAGUE_CODES.get(league, (None,))[0]
    if fd_code:
        season_year = match_date.year if match_date.month >= 8 else match_date.year - 1
        season_code = f"{str(season_year)[2:]}{str(season_year + 1)[2:]}"
        async with aiohttp.ClientSession() as session:
            rows = await fetch_football_data_csv(session, season_code, fd_code)
        if rows:
            parsed = [
                p for r in rows
                if (p := parse_football_data_row(r, league, "")) is not None
            ]
            found = await _find_in_list(parsed)
            if found:
                result.update({k: v for k, v in found.items() if v is not None and k not in ("league", "season", "match_date", "home_team", "away_team")})

    # 2) Understat – xG
    us_slug = LEAGUE_CODES.get(league, (None, None))[1]
    if us_slug:
        season_year = match_date.year if match_date.month >= 8 else match_date.year - 1
        async with aiohttp.ClientSession() as session:
            us_matches = await fetch_understat_league(session, us_slug, season_year)
        found = await _find_in_list(us_matches)
        if found:
            if found.get("xg_home") is not None:
                result["xg_home"] = found["xg_home"]
                result["xg_away"] = found["xg_away"]
            # Understat also has goals – use as fallback
            if "home_goals" not in result and found.get("home_goals") is not None:
                result["home_goals"] = found["home_goals"]
                result["away_goals"] = found["away_goals"]

    # 3) FBRef – standard score fallback
    if "home_goals" not in result:
        from app.services.data_scraper import scrape_fbref_results
        try:
            fbref_matches = await scrape_fbref_results(league, seasons_back=1)
            found = await _find_in_list(fbref_matches)
            if found and found.get("home_goals") is not None:
                result["home_goals"] = found["home_goals"]
                result["away_goals"] = found["away_goals"]
        except Exception:
            pass

    # 4) ESPN – score, basic result (only completed matches)
    espn_slug = ESPN_LEAGUE_SLUGS.get(league)
    if espn_slug and "home_goals" not in result:
        async with aiohttp.ClientSession() as session:
            events = await _fetch_espn_results_chunk(
                session, espn_slug, date_key, date_key
            )
        for event in events:
            try:
                # Only use data from completed matches
                completed = event.get("status", {}).get("type", {}).get("completed", False)
                if not completed:
                    continue

                comp = event.get("competitions", [{}])[0]
                eh = ea = eg_h = eg_a = None
                for c in comp.get("competitors", []):
                    name = c.get("team", {}).get("displayName", "")
                    score = c.get("score", "")
                    if c.get("homeAway") == "home":
                        eh = _normalize(name)
                        eg_h = int(score) if score else None
                    else:
                        ea = _normalize(name)
                        eg_a = int(score) if score else None
                if eh and ea and (
                    (h_norm in eh or eh in h_norm) and (a_norm in ea or ea in a_norm)
                ):
                    if eg_h is not None:
                        result["home_goals"] = eg_h
                        result["away_goals"] = eg_a
                    break
            except Exception:
                continue

    # Determine status
    if result.get("home_goals") is not None:
        result["status"] = "finished"

    return result
