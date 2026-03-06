from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date


# ─── League ──────────────────────────────────────────────────────────────────
class LeagueBase(BaseModel):
    name: str
    country: Optional[str] = None
    season: Optional[str] = None
    logo_url: Optional[str] = None


class LeagueCreate(LeagueBase):
    pass


class LeagueOut(LeagueBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Team ─────────────────────────────────────────────────────────────────────
class TeamBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    logo_url: Optional[str] = None
    league_id: Optional[int] = None
    country: Optional[str] = None
    manager: Optional[str] = None
    stadium: Optional[str] = None


class TeamCreate(TeamBase):
    pass


class TeamOut(TeamBase):
    id: int
    elo_rating: float
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Match ─────────────────────────────────────────────────────────────────────
class MatchBase(BaseModel):
    home_team_id: int
    away_team_id: int
    league_id: int
    match_date: datetime
    season: str
    matchday: Optional[int] = None
    status: str = "scheduled"


class MatchCreate(MatchBase):
    pass


class MatchUpdate(BaseModel):
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    shots_home: Optional[int] = None
    shots_away: Optional[int] = None
    shots_on_target_home: Optional[int] = None
    shots_on_target_away: Optional[int] = None
    possession_home: Optional[float] = None
    possession_away: Optional[float] = None
    odds_home_open: Optional[float] = None
    odds_draw_open: Optional[float] = None
    odds_away_open: Optional[float] = None
    odds_home_close: Optional[float] = None
    odds_draw_close: Optional[float] = None
    odds_away_close: Optional[float] = None
    odds_over25: Optional[float] = None
    odds_under25: Optional[float] = None
    odds_btts_yes: Optional[float] = None
    odds_btts_no: Optional[float] = None
    status: Optional[str] = None


class MatchOut(MatchBase):
    id: int
    home_goals: Optional[int]
    away_goals: Optional[int]
    xg_home: Optional[float]
    xg_away: Optional[float]
    shots_home: Optional[int]
    shots_away: Optional[int]
    shots_on_target_home: Optional[int]
    shots_on_target_away: Optional[int]
    possession_home: Optional[float]
    possession_away: Optional[float]
    odds_home_close: Optional[float]
    odds_draw_close: Optional[float]
    odds_away_close: Optional[float]
    odds_over25: Optional[float]
    odds_under25: Optional[float]
    odds_btts_yes: Optional[float]
    odds_btts_no: Optional[float]
    home_team: Optional[TeamOut]
    away_team: Optional[TeamOut]
    league: Optional[LeagueOut]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── TeamStats ─────────────────────────────────────────────────────────────────
class TeamStatsOut(BaseModel):
    id: int
    team_id: int
    season: Optional[str]
    goals_scored: float
    goals_conceded: float
    xg_for: float
    xg_against: float
    shots_per_game: float
    shots_on_target_pct: float
    big_chances_created: float
    shot_conversion_rate: float
    clean_sheet_pct: float
    btts_pct: float
    ppda: float
    home_goals_scored: float
    home_goals_conceded: float
    away_goals_scored: float
    away_goals_conceded: float
    form_last_5: Optional[str]
    form_last_10: Optional[str]
    rolling5_xg_for: float
    rolling5_xg_against: float
    rolling10_xg_for: float
    rolling10_xg_against: float
    matches_played: int
    wins: int
    draws: int
    losses: int
    points: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Player ─────────────────────────────────────────────────────────────────────
class PlayerBase(BaseModel):
    name: str
    team_id: Optional[int] = None
    nationality: Optional[str] = None
    position: Optional[str] = None
    age: Optional[int] = None
    number: Optional[int] = None


class PlayerCreate(PlayerBase):
    pass


class PlayerOut(PlayerBase):
    id: int
    team_name: Optional[str] = None
    xg_per90: float
    xa_per90: float
    goals_per90: float
    assists_per90: float
    progressive_passes: float
    defensive_duels_won: float
    is_injured: bool
    injury_detail: Optional[str]
    injury_return: Optional[date]
    is_suspended: bool
    suspension_matches: int
    rotation_risk: bool
    matches_played: int
    goals: int
    assists: int
    minutes_played: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Prediction ─────────────────────────────────────────────────────────────────
class PredictionRequest(BaseModel):
    match_id: int
    model: str = "dixon_coles"
    include_betting: bool = True


class ScoreMatrix(BaseModel):
    matrix: Dict[str, float]  # {"0-0": 0.032, ...}
    most_likely_score: str
    top_5_scores: List[Dict[str, float]]


class ValueBet(BaseModel):
    market: str
    model_prob: float
    market_prob: float
    edge_pct: float
    odds: float
    kelly_fraction: float
    is_value: bool


class PredictionOut(BaseModel):
    id: int
    match_id: int
    model_used: str
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    expected_goals_home: float
    expected_goals_away: float
    expected_goals_total: float
    prob_over25: float
    prob_under25: float
    prob_btts_yes: float
    prob_btts_no: float
    score_matrix: Optional[Dict[str, float]]
    value_bets: Optional[List[ValueBet]]
    confidence: Optional[float]
    notes: Optional[str]
    match: Optional[MatchOut]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Bankroll ─────────────────────────────────────────────────────────────────
class KellyInput(BaseModel):
    bankroll: float = Field(..., gt=0)
    model_probability: float = Field(..., ge=0, le=1)
    decimal_odds: float = Field(..., gt=1)
    fraction: float = Field(0.25, ge=0.01, le=1.0, description="Kelly fraction (0.25 = quarter Kelly)")


class KellyOut(BaseModel):
    full_kelly: float
    fractional_kelly: float
    stake_amount: float
    expected_value: float
    edge_pct: float
    ruin_risk: str


# ─── Dashboard Stats ─────────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_matches: int
    total_predictions: int
    predictions_last_7_days: int
    average_model_accuracy: float
    top_value_bets: List[Dict]
    upcoming_matches: List[Dict]
    recent_predictions: List[Dict]
