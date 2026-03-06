from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
import json
import logging

from app.database import get_db
from app.models.models import Match, Prediction, League
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _empty_stats():
    return {
        "total_matches": 0, "total_predictions": 0,
        "predictions_last_7_days": 0, "upcoming_count": 0,
        "league_distribution": [], "upcoming_matches": [],
        "high_confidence_predictions": [],
        "db_status": "unavailable",
    }


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the dashboard overview."""
    try:
        total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0
    except Exception:
        return _empty_stats()
    total_predictions = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_preds = (
        await db.execute(
            select(func.count(Prediction.id)).where(Prediction.created_at >= week_ago)
        )
    ).scalar() or 0

    # Upcoming matches (next 7 days)
    now = datetime.now(timezone.utc)
    upcoming_q = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(
            and_(
                Match.match_date >= now,
                Match.match_date <= now + timedelta(days=7),
                Match.status == "scheduled",
            )
        )
        .order_by(Match.match_date)
        .limit(5)
    )
    upcoming_result = await db.execute(upcoming_q)
    upcoming = upcoming_result.scalars().all()

    # Recent predictions
    recent_preds_q = (
        select(Prediction)
        .order_by(desc(Prediction.created_at))
        .limit(5)
    )
    recent_preds_result = await db.execute(recent_preds_q)
    recent_predictions = recent_preds_result.scalars().all()

    # League counts
    league_counts_q = select(League.name, func.count(Match.id)).join(
        Match, Match.league_id == League.id
    ).group_by(League.name).order_by(desc(func.count(Match.id)))
    league_counts = (await db.execute(league_counts_q)).all()

    # Best value bets (high confidence predictions)
    value_q = (
        select(Prediction)
        .where(Prediction.confidence >= 60)
        .order_by(desc(Prediction.confidence))
        .limit(5)
    )
    value_result = await db.execute(value_q)
    value_preds = value_result.scalars().all()

    return {
        "total_matches": total_matches,
        "total_predictions": total_predictions,
        "predictions_last_7_days": recent_preds,
        "upcoming_count": len(upcoming),
        "league_distribution": [{"league": row[0], "match_count": row[1]} for row in league_counts],
        "upcoming_matches": [
            {
                "match_id": m.id,
                "date": m.match_date.isoformat() if m.match_date else None,
                "home_team_id": m.home_team_id,
                "away_team_id": m.away_team_id,
                "home_team": m.home_team.name if m.home_team else None,
                "away_team": m.away_team.name if m.away_team else None,
                "league_id": m.league_id,
                "season": m.season,
            }
            for m in upcoming
        ],
        "high_confidence_predictions": [
            {
                "prediction_id": p.id,
                "match_id": p.match_id,
                "confidence": p.confidence,
                "prob_home_win": p.prob_home_win,
                "prob_draw": p.prob_draw,
                "prob_away_win": p.prob_away_win,
                "expected_goals_total": p.expected_goals_total,
            }
            for p in value_preds
        ],
    }


def _pred_to_pick(p, m):
    """Convert a Prediction + its Match to a pick dict."""
    probs = {
        "home": p.prob_home_win or 0,
        "draw": p.prob_draw or 0,
        "away": p.prob_away_win or 0,
    }
    best = max(probs, key=probs.get)
    label_map = {"home": "Home Win", "draw": "Draw", "away": "Away Win"}
    return {
        "match_id": m.id,
        "home_team": m.home_team.name if m.home_team else f"#{m.home_team_id}",
        "away_team": m.away_team.name if m.away_team else f"#{m.away_team_id}",
        "date": m.match_date.isoformat() if m.match_date else None,
        "league": m.league.name if m.league else None,
        "season": m.season,
        "confidence": round(p.confidence or 0, 1),
        "predicted_outcome": label_map[best],
        "prob": round(probs[best] * 100, 1),
        "prob_home_win": p.prob_home_win,
        "prob_draw": p.prob_draw,
        "prob_away_win": p.prob_away_win,
        "expected_goals_total": p.expected_goals_total,
    }


@router.get("/pick-of-the-day")
async def pick_of_the_day(db: AsyncSession = Depends(get_db)):
    """Return the top model pick + an AI-selected pick from remaining upcoming predictions."""
    now = datetime.now(timezone.utc)

    # All upcoming matches that have predictions, ordered by confidence
    q = (
        select(Prediction, Match)
        .join(Match, Prediction.match_id == Match.id)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
        )
        .where(
            and_(
                Match.match_date >= now,
                Match.status == "scheduled",
            )
        )
        .order_by(desc(Prediction.confidence))
        .limit(10)
    )
    rows = (await db.execute(q)).all()

    if not rows:
        return {"picks": [], "ai_reasoning": None}

    # First pick: highest confidence
    top_pred, top_match = rows[0]
    top_pick = _pred_to_pick(top_pred, top_match)
    top_pick["pick_type"] = "model"
    top_pick["pick_label"] = "Top Model Pick"

    picks = [top_pick]

    # If there are more candidates, ask AI to choose the best secondary pick
    if len(rows) > 1 and settings.GROQ_API_KEY:
        candidates = []
        for pred, match in rows[1:]:
            candidates.append(_pred_to_pick(pred, match))

        ai_pick, reasoning = await _ai_select_pick(candidates)
        if ai_pick:
            ai_pick["pick_type"] = "ai"
            ai_pick["pick_label"] = "AI Pick"
            picks.append(ai_pick)
            return {"picks": picks, "ai_reasoning": reasoning}

    # Fallback: second-highest confidence if AI unavailable
    if len(rows) > 1:
        second_pred, second_match = rows[1]
        second_pick = _pred_to_pick(second_pred, second_match)
        second_pick["pick_type"] = "model"
        second_pick["pick_label"] = "Runner-Up"
        picks.append(second_pick)

    return {"picks": picks, "ai_reasoning": None}


async def _ai_select_pick(candidates):
    """Ask AI to choose the most interesting pick from candidates."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

        summary = json.dumps(
            [
                {
                    "idx": i,
                    "match": f"{c['home_team']} vs {c['away_team']}",
                    "league": c.get("league"),
                    "confidence": c["confidence"],
                    "predicted_outcome": c["predicted_outcome"],
                    "prob": c["prob"],
                    "xG_total": c.get("expected_goals_total"),
                }
                for i, c in enumerate(candidates)
            ],
            indent=2,
        )

        resp = await client.chat.completions.create(
            model=settings.GROQ_MODEL or "deepseek-r1-distill-llama-70b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a football betting analyst. Given a list of upcoming matches with "
                        "model predictions, pick THE ONE match that offers the best combination of "
                        "value, confidence, and interesting narrative. Respond in EXACTLY this JSON format:\n"
                        '{"idx": <number>, "reason": "<one sentence why this is the pick>"}'
                    ),
                },
                {"role": "user", "content": f"Choose the best pick from:\n{summary}"},
            ],
            max_tokens=150,
            temperature=0.5,
        )

        content = resp.choices[0].message.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        # Handle think blocks
        if "<think>" in content:
            content = content.split("</think>")[-1].strip()
        result = json.loads(content)
        idx = int(result["idx"])
        if 0 <= idx < len(candidates):
            return candidates[idx], result.get("reason")
    except Exception as e:
        logger.warning(f"AI pick selection failed: {e}")

    return None, None
