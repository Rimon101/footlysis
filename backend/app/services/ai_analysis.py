"""
AI-powered match analysis – combines prediction engine output with
pre-match analysis data to generate natural-language insights.
"""

import json
import logging
import re
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(prediction: Dict, analysis: Dict, match_info: Dict) -> str:
    """Build a structured prompt from prediction + analysis data."""

    home = match_info.get("home_team", "Home")
    away = match_info.get("away_team", "Away")
    league = match_info.get("league", "")

    sections = [
        f"You are a professional football analyst. Analyse this upcoming {league} match: {home} vs {away}.",
        "",
        "Use the statistical data below to write a detailed, insightful pre-match analysis.",
        "Be specific with numbers. Identify key patterns and trends.",
        "Structure your response with these sections:",
        "1. **Match Overview** – who is favoured and why (2-3 sentences)",
        "2. **Form & Momentum** – recent form comparison with specific results",
        "3. **Key Stats** – xG trends, scoring patterns, defensive records",
        "4. **Head-to-Head** – historical matchup trends",
        "5. **Goals Market** – over/under 2.5 & BTTS analysis with reasoning",
        "6. **Prediction** – your predicted scoreline with confidence reasoning",
        "7. **Value Insights** – any betting angles the model highlights",
        "",
        "─── PREDICTION ENGINE DATA ───",
    ]

    # Prediction data
    pred_summary = {
        "model": prediction.get("model_used", "dixon_coles"),
        "home_win_prob": prediction.get("prob_home_win"),
        "draw_prob": prediction.get("prob_draw"),
        "away_win_prob": prediction.get("prob_away_win"),
        "expected_goals_home": prediction.get("expected_goals_home"),
        "expected_goals_away": prediction.get("expected_goals_away"),
        "expected_goals_total": prediction.get("expected_goals_total"),
        "over_2.5_prob": prediction.get("prob_over25"),
        "btts_prob": prediction.get("prob_btts_yes"),
        "most_likely_score": prediction.get("most_likely_score"),
        "top_5_scores": prediction.get("top5_scores"),
        "confidence": prediction.get("confidence"),
        "home_momentum": prediction.get("home_momentum"),
        "away_momentum": prediction.get("away_momentum"),
        "home_elo": prediction.get("elo_home"),
        "away_elo": prediction.get("elo_away"),
    }
    sections.append(json.dumps(pred_summary, indent=2))

    # Form data
    if prediction.get("home_form"):
        sections.append("\n─── HOME TEAM FORM ───")
        sections.append(json.dumps(prediction["home_form"], indent=2, default=str))
    if prediction.get("away_form"):
        sections.append("\n─── AWAY TEAM FORM ───")
        sections.append(json.dumps(prediction["away_form"], indent=2, default=str))

    # Value bets
    if prediction.get("value_bets"):
        sections.append("\n─── VALUE BETS (Kelly Criterion) ───")
        sections.append(json.dumps(prediction["value_bets"], indent=2, default=str))

    # Analysis data (if available)
    if analysis:
        sections.append("\n─── PRE-MATCH ANALYSIS DATA ───")

        # H2H
        if analysis.get("h2h_summary"):
            sections.append(f"\nHead-to-Head Summary: {json.dumps(analysis['h2h_summary'])}")

        # Form strings
        for key in ["home_form", "away_form", "home_form_10", "away_form_10"]:
            if analysis.get(key):
                sections.append(f"{key}: {analysis[key]}")

        # Records
        for key in ["home_overall", "away_overall", "home_at_home", "away_at_away",
                     "home_last5", "away_last5"]:
            if analysis.get(key):
                sections.append(f"{key}: {json.dumps(analysis[key])}")

        # Goals distribution
        for key in ["home_goals_dist", "away_goals_dist"]:
            if analysis.get(key):
                sections.append(f"{key}: {json.dumps(analysis[key])}")

        # Streaks
        for key in ["home_streaks", "away_streaks"]:
            if analysis.get(key):
                sections.append(f"{key}: {json.dumps(analysis[key])}")

        # Team stats from DB
        for key in ["home_stats", "away_stats"]:
            if analysis.get(key):
                sections.append(f"{key}: {json.dumps(analysis[key], default=str)}")

        # Shots / corners / cards (summarised)
        for key in ["home_shots", "away_shots", "home_corners", "away_corners"]:
            if analysis.get(key):
                sections.append(f"{key}: {json.dumps(analysis[key])}")

    sections.append("\n─── END DATA ───")
    sections.append("\nWrite the analysis now. Use markdown formatting. Be concise but insightful.")
    sections.append(
        "\nIMPORTANT: At the very end of your response, on its own line, output exactly this marker "
        "followed by a single-line JSON object (no newlines inside the JSON):\n"
        "CHART_JSON: {\"home_win_pct\": <int>, \"draw_pct\": <int>, \"away_win_pct\": <int>, "
        "\"predicted_score\": \"<home_goals>-<away_goals>\", \"confidence\": \"<Low|Medium|High>\", "
        "\"over25_pct\": <int>, \"btts_pct\": <int>, "
        "\"key_factors\": [\"<short factor 1>\", \"<short factor 2>\", \"<short factor 3>\"]}\n"
        "Fill in the integers and strings based on your analysis. Do not add any text after the JSON."
    )

    return "\n".join(sections)


# ── OpenAI integration ────────────────────────────────────────────────────────

async def generate_ai_analysis(
    prediction: Dict,
    analysis: Optional[Dict],
    match_info: Dict,
) -> Dict:
    """
    Generate AI-powered match analysis combining prediction engine
    output with pre-match analysis data.

    Returns dict with 'ai_analysis' (markdown string) and 'status'.
    """
    if not settings.GROQ_API_KEY:
        return {
            "status": "no_api_key",
            "ai_analysis": None,
            "message": "Groq API key not configured. Set GROQ_API_KEY in your .env file.",
        }

    prompt = _build_prompt(prediction, analysis or {}, match_info)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

        response = await client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an elite football data analyst. You combine statistical models "
                        "(Dixon-Coles, Poisson, Elo) with match data to produce sharp, data-driven "
                        "pre-match analyses. Be specific with numbers. Never fabricate statistics — "
                        "only reference data provided to you."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.7,
        )

        content = response.choices[0].message.content

        # Extract structured chart data from CHART_JSON marker
        chart_data = None
        idx = content.rfind("CHART_JSON:")
        if idx != -1:
            remainder = content[idx + len("CHART_JSON:"):].strip()
            brace_start = remainder.find("{")
            if brace_start != -1:
                try:
                    decoder = json.JSONDecoder()
                    chart_data, _ = decoder.raw_decode(remainder[brace_start:])
                    content = content[:idx].strip()
                except Exception as parse_err:
                    logger.warning(f"Failed to parse chart JSON: {parse_err}")

        return {
            "status": "success",
            "ai_analysis": content,
            "chart_data": chart_data,
            "tokens_used": response.usage.total_tokens if response.usage else None,
        }

    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        return {"status": "error", "ai_analysis": None, "message": "openai package not installed"}
    except Exception as e:
        logger.error(f"AI analysis generation failed: {e}")
        return {"status": "error", "ai_analysis": None, "message": str(e)}
