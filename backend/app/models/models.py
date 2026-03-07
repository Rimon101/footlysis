from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.database import Base

class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    country = Column(String(100))
    season = Column(String(20))
    logo_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    teams = relationship("Team", back_populates="league")
    matches = relationship("Match", back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    short_name = Column(String(50))
    logo_url = Column(String(500))
    league_id = Column(Integer, ForeignKey("leagues.id"))
    country = Column(String(100))
    founded = Column(Integer)
    stadium = Column(String(200))
    stadium_capacity = Column(Integer)
    manager = Column(String(200))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Stats
    elo_rating = Column(Float, default=1500.0)
    home_elo = Column(Float, default=1500.0)
    away_elo = Column(Float, default=1500.0)

    league = relationship("League", back_populates="teams")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")
    players = relationship("Player", back_populates="team")
    stats = relationship("TeamStats", back_populates="team", uselist=False)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("league_id", "home_team_id", "away_team_id", "match_date", name="uq_match_fixture"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    match_date = Column(DateTime(timezone=True), nullable=False)
    season = Column(String(20), nullable=False)
    matchday = Column(Integer)
    status = Column(String(20), default="scheduled")  # scheduled, live, finished

    # Full Time
    home_goals = Column(Integer)
    away_goals = Column(Integer)

    # Half Time
    ht_home_goals = Column(Integer)
    ht_away_goals = Column(Integer)

    # xG
    xg_home = Column(Float)
    xg_away = Column(Float)

    # Shots
    shots_home = Column(Integer)
    shots_away = Column(Integer)
    shots_on_target_home = Column(Integer)
    shots_on_target_away = Column(Integer)

    # Possession
    possession_home = Column(Float)
    possession_away = Column(Float)

    # Corners, Fouls, Cards
    corners_home = Column(Integer)
    corners_away = Column(Integer)
    fouls_home = Column(Integer)
    fouls_away = Column(Integer)
    yellow_home = Column(Integer)
    yellow_away = Column(Integer)
    red_home = Column(Integer)
    red_away = Column(Integer)

    # Odds at open
    odds_home_open = Column(Float)
    odds_draw_open = Column(Float)
    odds_away_open = Column(Float)

    # Odds at close
    odds_home_close = Column(Float)
    odds_draw_close = Column(Float)
    odds_away_close = Column(Float)

    # Over/Under odds
    odds_over25 = Column(Float)
    odds_under25 = Column(Float)

    # BTTS odds
    odds_btts_yes = Column(Float)
    odds_btts_no = Column(Float)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    league = relationship("League", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    prediction = relationship("Prediction", back_populates="match", uselist=False)


class TeamStats(Base):
    __tablename__ = "team_stats"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), unique=True)
    season = Column(String(20))

    # Attack
    goals_scored = Column(Float, default=0)
    goals_conceded = Column(Float, default=0)
    xg_for = Column(Float, default=0)
    xg_against = Column(Float, default=0)
    shots_per_game = Column(Float, default=0)
    shots_on_target_pct = Column(Float, default=0)
    big_chances_created = Column(Float, default=0)
    shot_conversion_rate = Column(Float, default=0)

    # Defence
    clean_sheet_pct = Column(Float, default=0)
    btts_pct = Column(Float, default=0)
    ppda = Column(Float, default=0)  # passes per defensive action

    # Home/Away Splits
    home_goals_scored = Column(Float, default=0)
    home_goals_conceded = Column(Float, default=0)
    away_goals_scored = Column(Float, default=0)
    away_goals_conceded = Column(Float, default=0)

    # Form (rolling)
    form_last_5 = Column(String(20))  # e.g. "WWDLW"
    form_last_10 = Column(String(30))
    rolling5_xg_for = Column(Float, default=0)
    rolling5_xg_against = Column(Float, default=0)
    rolling10_xg_for = Column(Float, default=0)
    rolling10_xg_against = Column(Float, default=0)

    # Record
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    points = Column(Integer, default=0)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="stats")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    nationality = Column(String(100))
    position = Column(String(50))
    age = Column(Integer)
    number = Column(Integer)
    photo_url = Column(String(500))

    # Impact metrics per 90
    xg_per90 = Column(Float, default=0)
    xa_per90 = Column(Float, default=0)
    goals_per90 = Column(Float, default=0)
    assists_per90 = Column(Float, default=0)
    progressive_passes = Column(Float, default=0)
    defensive_duels_won = Column(Float, default=0)
    key_passes_per90 = Column(Float, default=0)
    shots_per90 = Column(Float, default=0)

    # Availability
    is_injured = Column(Boolean, default=False)
    injury_detail = Column(String(500))
    injury_return = Column(Date)
    is_suspended = Column(Boolean, default=False)
    suspension_matches = Column(Integer, default=0)
    rotation_risk = Column(Boolean, default=False)

    # Season Stats
    matches_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="players")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), unique=True)
    model_used = Column(String(50), default="dixon_coles")

    # Win probabilities
    prob_home_win = Column(Float)
    prob_draw = Column(Float)
    prob_away_win = Column(Float)

    # Goals
    expected_goals_home = Column(Float)
    expected_goals_away = Column(Float)
    expected_goals_total = Column(Float)

    # Markets
    prob_over25 = Column(Float)
    prob_under25 = Column(Float)
    prob_btts_yes = Column(Float)
    prob_btts_no = Column(Float)

    # Score matrix (stored as JSON string)
    score_matrix = Column(Text)  # JSON: {"0-0": 0.032, "1-0": 0.089, ...}

    # Value bets
    value_home = Column(Float)   # Edge % vs market
    value_draw = Column(Float)
    value_away = Column(Float)
    value_over25 = Column(Float)
    value_btts = Column(Float)

    # Kelly
    kelly_home = Column(Float)
    kelly_draw = Column(Float)
    kelly_away = Column(Float)

    confidence = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    match = relationship("Match", back_populates="prediction")
