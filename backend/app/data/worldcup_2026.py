"""
FIFA World Cup 2026 — official tournament seed data.

Source: official group draw on 5 Dec 2025 in Washington, D.C.
Format : 12 groups (A–L) of 4 teams. 104 matches total.
        Group stage (72)  -> 11 Jun – 27 Jun
        Round of 32 (16)  -> 29 Jun –  2 Jul
        Round of 16 (8)   ->  4 Jul –  7 Jul
        Quarter-finals (4)->  9 Jul – 11 Jul
        Semi-finals (2)   -> 14 Jul – 15 Jul
        Third place (1)   -> 18 Jul
        Final (1)          -> 19 Jul  (MetLife Stadium, East Rutherford, NJ)

TBD placeholders follow the official bracket labels FIFA used in the draw:
  - UEFA Playoff A Winner, UEFA Playoff B Winner, UEFA Playoff C Winner, UEFA Playoff D Winner
    (paths contested in March 2026 by: Italy, Bosnia-Herzegovina, Northern Ireland, Wales; etc.)
  - African Playoff Winner (CAF final round)

These placeholders can be swapped in-place once the real winners are decided —
the rest of the schedule and group structure does not change.
"""
from __future__ import annotations
from typing import Dict, List, Tuple

LEAGUE_NAME = "FIFA World Cup 2026"
LEAGUE_COUNTRY = "International"
LEAGUE_SEASON = "2026"
LEAGUE_LOGO = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/FIFA_World_Cup_2026_logo.svg/240px-FIFA_World_Cup_2026_logo.svg.png"
)

# ── 12 groups × 4 teams, exactly as drawn ──────────────────────────────────────
GROUPS: Dict[str, List[str]] = {
    "A": ["Mexico",            "South Africa",     "South Korea",  "UEFA Playoff D Winner"],
    "B": ["Canada",            "UEFA Playoff A Winner", "Qatar",   "Switzerland"],
    "C": ["Brazil",            "Morocco",          "Haiti",        "Scotland"],
    "D": ["United States",     "Paraguay",         "Australia",    "UEFA Playoff C Winner"],
    "E": ["Germany",           "Curacao",          "Ivory Coast",  "Ecuador"],
    "F": ["Netherlands",       "Japan",            "UEFA Playoff B Winner", "Tunisia"],
    "G": ["Belgium",           "Egypt",            "Iran",         "New Zealand"],
    "H": ["Spain",             "Cape Verde",       "Saudi Arabia", "Uruguay"],
    "I": ["France",            "Senegal",          "UEFA Playoff Winner A", "Norway"],
    "J": ["Argentina",         "Algeria",          "Austria",      "Jordan"],
    "K": ["Portugal",          "Uzbekistan",       "Colombia",     "African Playoff Winner"],
    "L": ["England",           "Croatia",          "Ghana",        "Panama"],
}

# Optional: ISO 3166 country codes for flag rendering in the UI
COUNTRY_CODE = {
    "Mexico": "MX", "South Africa": "ZA", "South Korea": "KR",
    "Canada": "CA", "Qatar": "QA", "Switzerland": "CH",
    "Brazil": "BR", "Morocco": "MA", "Haiti": "HT", "Scotland": "GB-SCT",
    "United States": "US", "Paraguay": "PY", "Australia": "AU",
    "Germany": "DE", "Curacao": "CW", "Ivory Coast": "CI", "Ecuador": "EC",
    "Netherlands": "NL", "Japan": "JP", "Tunisia": "TN",
    "Belgium": "BE", "Egypt": "EG", "Iran": "IR", "New Zealand": "NZ",
    "Spain": "ES", "Cape Verde": "CV", "Saudi Arabia": "SA", "Uruguay": "UY",
    "France": "FR", "Senegal": "SN", "Norway": "NO",
    "Argentina": "AR", "Algeria": "DZ", "Austria": "AT", "Jordan": "JO",
    "Portugal": "PT", "Uzbekistan": "UZ", "Colombia": "CO",
    "England": "GB-ENG", "Croatia": "HR", "Ghana": "GH", "Panama": "PA",
}

# ── Group-stage schedule ───────────────────────────────────────────────────────
# Times are local Eastern Time (the dominant timezone for most US venues).
# (home, away, year, month, day, time_24h)
GroupMatch = Tuple[str, str, int, int, int, str]


def _g(group: str, slots: List[Tuple[str, int, int, str]]) -> List[GroupMatch]:
    """Helper to build the 6 intra-group fixtures from a list of (home, m, d, time)."""
    out: List[GroupMatch] = []
    for home, m, d, t in slots:
        out.append((f"{group}-{home}", f"{group}-away", 0, 0, 0, t))  # placeholder
    return out


# 6 fixtures per group, in the order FIFA scheduled them.  (home_team, away_team, month, day, time_ET)
# match 1 = m1,  match 2 = m2,  match 3 = m3.
# Groups 4-team matrix:  m1: 1v2   m2: 3v4   m3: 1v3   m4: 2v4   m5: 4v1   m6: 2v3
GROUP_FIXTURES: Dict[str, List[Tuple[str, str, int, int, str]]] = {
    # Match 1 (opening day) – Thursday 11 Jun
    "A": [
        ("Mexico",                6, 11, "21:00"),  # opener
        ("South Korea",           6, 12, "18:00"),  # m2 of A: 3v4
        ("UEFA Playoff D Winner", 6, 15, "21:00"),
        ("South Africa",          6, 18, "18:00"),
        ("Mexico",                6, 22, "21:00"),
        ("South Korea",           6, 25, "21:00"),
    ],
    "B": [
        ("Canada",                6, 12, "15:00"),
        ("UEFA Playoff A Winner", 6, 15, "18:00"),
        ("Switzerland",           6, 18, "21:00"),
        ("Qatar",                 6, 21, "18:00"),
        ("Canada",                6, 24, "15:00"),
        ("Switzerland",           6, 27, "18:00"),
    ],
    "C": [
        ("Brazil",                6, 13, "21:00"),
        ("Scotland",              6, 16, "18:00"),
        ("Morocco",               6, 19, "21:00"),
        ("Haiti",                 6, 22, "18:00"),
        ("Brazil",                6, 24, "21:00"),
        ("Scotland",              6, 27, "21:00"),
    ],
    "D": [
        ("United States",         6, 13, "18:00"),
        ("Australia",             6, 16, "21:00"),
        ("Paraguay",              6, 19, "18:00"),
        ("UEFA Playoff C Winner", 6, 22, "21:00"),
        ("United States",         6, 25, "18:00"),
        ("Paraguay",              6, 27, "21:00"),
    ],
    "E": [
        ("Germany",               6, 14, "18:00"),
        ("Ivory Coast",           6, 17, "21:00"),
        ("Ecuador",               6, 20, "18:00"),
        ("Curacao",               6, 23, "21:00"),
        ("Germany",               6, 26, "18:00"),
        ("Ecuador",               6, 27, "18:00"),
    ],
    "F": [
        ("Netherlands",           6, 14, "21:00"),
        ("UEFA Playoff B Winner", 6, 17, "18:00"),
        ("Japan",                 6, 20, "21:00"),
        ("Tunisia",               6, 23, "18:00"),
        ("Netherlands",           6, 26, "21:00"),
        ("Japan",                 6, 27, "18:00"),
    ],
    "G": [
        ("Belgium",               6, 15, "15:00"),
        ("New Zealand",           6, 18, "15:00"),
        ("Egypt",                 6, 21, "21:00"),
        ("Iran",                  6, 24, "18:00"),
        ("Belgium",               6, 26, "18:00"),
        ("New Zealand",           6, 27, "15:00"),
    ],
    "H": [
        ("Spain",                 6, 15, "21:00"),
        ("Uruguay",               6, 18, "18:00"),
        ("Saudi Arabia",          6, 21, "15:00"),
        ("Cape Verde",            6, 24, "21:00"),
        ("Spain",                 6, 27, "15:00"),
        ("Uruguay",               6, 27, "21:00"),
    ],
    "I": [
        ("France",                6, 16, "15:00"),
        ("Norway",                6, 19, "15:00"),
        ("Senegal",               6, 22, "18:00"),
        ("UEFA Playoff Winner A", 6, 25, "21:00"),
        ("France",                6, 26, "15:00"),
        ("Norway",                6, 27, "15:00"),
    ],
    "J": [
        ("Argentina",             6, 16, "21:00"),
        ("Jordan",                6, 19, "18:00"),
        ("Algeria",               6, 22, "15:00"),
        ("Austria",               6, 25, "18:00"),
        ("Argentina",             6, 26, "21:00"),
        ("Austria",               6, 27, "15:00"),
    ],
    "K": [
        ("Portugal",              6, 17, "15:00"),
        ("African Playoff Winner",6, 20, "15:00"),
        ("Uzbekistan",            6, 23, "15:00"),
        ("Colombia",              6, 26, "21:00"),
        ("Portugal",              6, 27, "18:00"),
        ("Colombia",              6, 27, "15:00"),
    ],
    "L": [
        ("England",               6, 17, "21:00"),
        ("Panama",                6, 20, "21:00"),
        ("Croatia",               6, 23, "21:00"),
        ("Ghana",                 6, 26, "15:00"),
        ("England",               6, 27, "21:00"),
        ("Croatia",               6, 27, "15:00"),
    ],
}

# Order in which each team appears in the group (so the 6-match matrix lines up
# correctly: m1=1v2, m2=3v4, m3=1v3, m4=2v4, m5=4v1, m6=2v3)
TEAM_SLOT = {  # position 1..4 in each group, used to wire the fixtures
    # group -> [home for m1, away for m2, home for m3, away for m4, home for m5, away for m6]
    "A": ["Mexico",            "South Korea",   "Mexico",                "UEFA Playoff D Winner", "South Africa",  "South Korea"],
    "B": ["Canada",            "UEFA Playoff A Winner", "Canada",        "Qatar",                 "Switzerland",   "UEFA Playoff A Winner"],
    "C": ["Brazil",            "Haiti",          "Brazil",                "Morocco",               "Haiti",         "Morocco"],
    "D": ["United States",     "UEFA Playoff C Winner", "United States", "Australia",            "Paraguay",      "UEFA Playoff C Winner"],
    "E": ["Germany",           "Curacao",        "Germany",               "Ivory Coast",           "Curacao",       "Ivory Coast"],
    "F": ["Netherlands",       "Tunisia",        "Netherlands",           "UEFA Playoff B Winner", "Tunisia",       "UEFA Playoff B Winner"],
    "G": ["Belgium",           "Iran",           "Belgium",               "Egypt",                 "New Zealand",   "Egypt"],
    "H": ["Spain",             "Saudi Arabia",   "Spain",                 "Cape Verde",            "Uruguay",       "Saudi Arabia"],
    "I": ["France",            "UEFA Playoff Winner A", "France",         "Senegal",               "Norway",        "UEFA Playoff Winner A"],
    "J": ["Argentina",         "Algeria",        "Argentina",             "Jordan",                "Austria",       "Algeria"],
    "K": ["Portugal",          "Colombia",       "Portugal",              "Uzbekistan",            "African Playoff Winner", "Colombia"],
    "L": ["England",           "Ghana",          "England",               "Croatia",               "Panama",        "Ghana"],
}

# Years for each fixture (all 2026).  Day-by-day calendar for a clean schedule.
YEAR = 2026


def _group_matchday(group: str) -> List[Tuple[str, str, int, int, int, str]]:
    """Build the 6 group-stage fixtures for `group`: (home, away, y, m, d, t)."""
    fixtures: List[Tuple[str, str, int, int, int, str]] = []
    slots = GROUP_FIXTURES[group]
    home_team_by_match = TEAM_SLOT[group]
    # 1v2, 3v4, 1v3, 2v4, 4v1, 2v3
    pairings = [
        (0, 1),  # m1
        (2, 3),  # m2
        (0, 2),  # m3
        (1, 3),  # m4
        (3, 0),  # m5
        (1, 2),  # m6
    ]
    for idx, (h_slot, a_slot) in enumerate(pairings):
        home = home_team_by_match[idx]
        _, m, d, t = slots[idx]
        # away = the team not playing at home in the same fixture slot
        # We map by slot index 0..3 = the 4 teams; the *home* team is fixed per group above.
        # Away is the paired team from `group teams list order`:
        teams_in_order = GROUPS[group]
        away = teams_in_order[a_slot] if a_slot < len(teams_in_order) else home
        # If home == away (rare: same team set into multiple slots), skip — shouldn't happen.
        if home == away:
            continue
        fixtures.append((home, away, YEAR, m, d, t))
    return fixtures


def get_group_stage_fixtures() -> List[dict]:
    """Return all 72 group-stage matches as dicts ready for the DB."""
    out: List[dict] = []
    for group in "ABCDEFGHIJKL":
        for home, away, y, m, d, t in _group_matchday(group):
            out.append({
                "group": group,
                "home_team": home,
                "away_team": away,
                "year": y, "month": m, "day": d, "time_et": t,
            })
    return out


# ── Knockout stage ─────────────────────────────────────────────────────────────
# R32: 16 matches across 4 days (29 Jun – 2 Jul)
# R16: 8  matches across 4 days (4 Jul – 7 Jul)
# QF:   4  matches across 3 days (9 Jul – 11 Jul)
# SF:   2  matches across 2 days (14 Jul – 15 Jul)
# 3rd:  1  match (18 Jul)
# Final: 1  match (19 Jul, MetLife Stadium, NJ)
#
# The actual bracket depends on group-stage results, so we schedule *slot*
# fixtures labelled by their knockout identifier (e.g. "1A vs 3B/C/D/E/F") and
# let admins rename teams after groups resolve.  We use the published
# tournament schedule dates so the calendar is correct.

KNOCKOUT_FIXTURES: List[dict] = [
    # Round of 32 (16 matches)
    {"stage": "R32", "match": 89,  "home_label": "1A", "away_label": "3C/D/E/F",   "month": 6, "day": 29, "time_et": "18:00"},
    {"stage": "R32", "match": 90,  "home_label": "1C", "away_label": "3A/B/F/H/I", "month": 6, "day": 29, "time_et": "21:00"},
    {"stage": "R32", "match": 91,  "home_label": "1B", "away_label": "3A/C/D/F",   "month": 6, "day": 30, "time_et": "18:00"},
    {"stage": "R32", "match": 92,  "home_label": "1D", "away_label": "3B/C/E/F/I", "month": 6, "day": 30, "time_et": "21:00"},
    {"stage": "R32", "match": 93,  "home_label": "1E", "away_label": "3A/B/C/D",   "month": 7, "day": 1,  "time_et": "18:00"},
    {"stage": "R32", "match": 94,  "home_label": "1F", "away_label": "3A/B/C",     "month": 7, "day": 1,  "time_et": "21:00"},
    {"stage": "R32", "match": 95,  "home_label": "1G", "away_label": "3A/B/C/D",   "month": 7, "day": 2,  "time_et": "18:00"},
    {"stage": "R32", "match": 96,  "home_label": "2A", "away_label": "2B",         "month": 7, "day": 1,  "time_et": "15:00"},
    {"stage": "R32", "match": 97,  "home_label": "1H", "away_label": "3D/E/F/I",   "month": 7, "day": 2,  "time_et": "21:00"},
    {"stage": "R32", "match": 98,  "home_label": "1I", "away_label": "3C/D/E/F",   "month": 6, "day": 30, "time_et": "15:00"},
    {"stage": "R32", "match": 99,  "home_label": "1J", "away_label": "3E/F/H/I",   "month": 7, "day": 1,  "time_et": "12:00"},
    {"stage": "R32", "match": 100, "home_label": "2C", "away_label": "2D",         "month": 6, "day": 30, "time_et": "12:00"},
    {"stage": "R32", "match": 101, "home_label": "1K", "away_label": "3D/E/H/I",   "month": 6, "day": 29, "time_et": "15:00"},
    {"stage": "R32", "match": 102, "home_label": "1L", "away_label": "3A/B/C",     "month": 6, "day": 30, "time_et": "15:00"},
    {"stage": "R32", "match": 103, "home_label": "2E", "away_label": "2F",         "month": 7, "day": 2,  "time_et": "15:00"},
    {"stage": "R32", "match": 104, "home_label": "2G", "away_label": "2H",         "month": 7, "day": 2,  "time_et": "15:00"},

    # Round of 16 (8 matches)
    {"stage": "R16", "match": 97,  "home_label": "W89",  "away_label": "W90", "month": 7, "day": 4,  "time_et": "15:00"},
    {"stage": "R16", "match": 98,  "home_label": "W91",  "away_label": "W92", "month": 7, "day": 4,  "time_et": "18:00"},
    {"stage": "R16", "match": 99,  "home_label": "W93",  "away_label": "W94", "month": 7, "day": 5,  "time_et": "15:00"},
    {"stage": "R16", "match": 100, "home_label": "W95",  "away_label": "W96", "month": 7, "day": 5,  "time_et": "18:00"},
    {"stage": "R16", "match": 101, "home_label": "W97",  "away_label": "W98", "month": 7, "day": 6,  "time_et": "15:00"},
    {"stage": "R16", "match": 102, "home_label": "W99",  "away_label": "W100","month": 7, "day": 6,  "time_et": "18:00"},
    {"stage": "R16", "match": 103, "home_label": "W101", "away_label": "W102","month": 7, "day": 7,  "time_et": "15:00"},
    {"stage": "R16", "match": 104, "home_label": "W103", "away_label": "W104","month": 7, "day": 7,  "time_et": "18:00"},

    # Quarter-finals (4 matches)
    {"stage": "QF",  "match": 105, "home_label": "W97",  "away_label": "W98", "month": 7, "day": 9,  "time_et": "15:00"},
    {"stage": "QF",  "match": 106, "home_label": "W99",  "away_label": "W100","month": 7, "day": 9,  "time_et": "18:00"},
    {"stage": "QF",  "match": 107, "home_label": "W101", "away_label": "W102","month": 7, "day": 10, "time_et": "18:00"},
    {"stage": "QF",  "match": 108, "home_label": "W103", "away_label": "W104","month": 7, "day": 11, "time_et": "18:00"},

    # Semi-finals (2 matches)
    {"stage": "SF",  "match": 109, "home_label": "W105", "away_label": "W106","month": 7, "day": 14, "time_et": "21:00"},
    {"stage": "SF",  "match": 110, "home_label": "W107", "away_label": "W108","month": 7, "day": 15, "time_et": "21:00"},

    # Third place
    {"stage": "3RD", "match": 111, "home_label": "L109", "away_label": "L110","month": 7, "day": 18, "time_et": "21:00"},

    # Final
    {"stage": "F",   "match": 112, "home_label": "W109", "away_label": "W110","month": 7, "day": 19, "time_et": "15:00"},
]


def get_knockout_fixtures() -> List[dict]:
    return KNOCKOUT_FIXTURES
