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


# ── System prompt ─────────────────────────────────────────────────────────────

ANALYST_SYSTEM_PROMPT = (
    "You are an elite professional football analyst AI.\n\n"
    "Your role is to analyze football matches using data, statistics, and tactical knowledge "
    "like a professional analyst working for a football club or betting syndicate.\n\n"
    "Always base your analysis on football analytics and statistical reasoning.\n\n"
    "Your expertise includes:\n"
    "1. Team Performance Analysis — Recent form (last 5-10 matches), Home vs Away performance, "
    "Goals scored and conceded, Possession trends, Shots and shots on target, xG and xGA.\n"
    "2. Tactical Analysis — Formations, Pressing intensity, Defensive line height, "
    "Counter attacking ability, Set piece strength.\n"
    "3. Squad Analysis — Key players, Injuries and suspensions, Player form, Squad depth, Rotation risk.\n"
    "4. Matchup Analysis — Head to head history, Tactical matchup between teams, "
    "Weakness exploitation, Style clash (possession vs counter teams).\n"
    "5. Advanced Metrics — xG, xGA, xPTS, PPDA, Shot creating actions, Possession value.\n"
    "6. Prediction Modeling — Estimate probabilities for Home win, Draw, Away win, "
    "Over/Under goals, Both teams to score.\n\n"
    "Always explain reasoning step by step. Never give random guesses. "
    "Always justify predictions using football logic and statistics. "
    "Be analytical, objective, and data-driven like a professional football data scientist. "
    "Never fabricate statistics — only reference data provided to you."
)

CONSENSUS_SYSTEM_PROMPT = (
    "You are the Chief Football Analyst leading a panel of AI experts. "
    "Your role is to synthesise multiple independent analyses into one "
    "definitive, highly accurate pre-match report. Identify consensus, "
    "resolve disagreements with data, and produce a prediction that is "
    "more reliable than any single model. Be specific with numbers. "
    "Never fabricate statistics — only reference data provided to you."
)

# ── Groq model registry ──────────────────────────────────────────────────────

GROQ_MODELS = {
    "llama-4-maverick": {
        "id": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "label": "Llama 4 Maverick",
    },
    "gpt-oss-120b": {
        "id": "openai/gpt-oss-120b",
        "label": "GPT OSS 120B",
    },
}

DEFAULT_MODEL = "llama-4-maverick"

# ── OpenAI integration ────────────────────────────────────────────────────────

async def generate_ai_analysis(
    prediction: Dict,
    analysis: Optional[Dict],
    match_info: Dict,
    model: str = DEFAULT_MODEL,
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

        model_entry = GROQ_MODELS.get(model, GROQ_MODELS[DEFAULT_MODEL])
        groq_model_id = model_entry["id"]
        logger.info(f"Using Groq model: {groq_model_id}")

        response = await client.chat.completions.create(
            model=groq_model_id,
            messages=[
                {
                    "role": "system",
                    "content": ANALYST_SYSTEM_PROMPT,
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


# ── Consensus (Multi-Model) Engine ───────────────────────────────────────────

def _build_synthesis_prompt(
    individual_analyses: Dict[str, str],
    match_info: Dict,
) -> str:
    """Build a prompt that asks the synthesiser to combine multiple AI analyses."""
    home = match_info.get("home_team", "Home")
    away = match_info.get("away_team", "Away")
    league = match_info.get("league", "")

    parts = [
        f"You are the CHIEF FOOTBALL ANALYST. Three independent AI analysts have each written "
        f"their own pre-match analysis for {home} vs {away} ({league}). "
        f"Your job is to synthesise their work into one DEFINITIVE analysis that is more accurate "
        f"than any individual one.",
        "",
        "Rules:",
        "- Where all three analysts AGREE, state the consensus confidently.",
        "- Where analysts DISAGREE, weigh the arguments and pick the most data-supported view. Explain why.",
        "- Identify insights that only one analyst spotted — include them if they are backed by data.",
        "- Your final prediction should be a SINGLE scoreline with a confidence level.",
        "- Be specific with numbers. Do NOT fabricate any statistics.",
        "",
        "Structure your response with these sections:",
        "1. **Consensus Overview** — what all models agree on",
        "2. **Key Disagreements** — where models differed and your resolution",
        "3. **Deep Insights** — unique findings from individual models",
        "4. **Form & Momentum Consensus**",
        "5. **Goals Market Verdict** — over/under 2.5 & BTTS with final reasoning",
        "6. **Final Prediction** — your definitive scoreline and confidence",
        "7. **Value Angles** — betting insights supported by multi-model agreement",
        "",
    ]

    for model_key, analysis_text in individual_analyses.items():
        label = GROQ_MODELS.get(model_key, {}).get("label", model_key)
        parts.append(f"═══ ANALYST: {label} ═══")
        parts.append(analysis_text)
        parts.append("")

    parts.append("═══ END OF INDIVIDUAL ANALYSES ═══")
    parts.append("")
    parts.append("Write your synthesised analysis now. Use markdown formatting.")
    parts.append(
        "\nIMPORTANT: At the very end of your response, on its own line, output exactly this marker "
        "followed by a single-line JSON object (no newlines inside the JSON):\n"
        "CHART_JSON: {\"home_win_pct\": <int>, \"draw_pct\": <int>, \"away_win_pct\": <int>, "
        "\"predicted_score\": \"<home_goals>-<away_goals>\", \"confidence\": \"<Low|Medium|High>\", "
        "\"over25_pct\": <int>, \"btts_pct\": <int>, "
        "\"key_factors\": [\"<short factor 1>\", \"<short factor 2>\", \"<short factor 3>\"]}\n"
        "Fill in the integers and strings based on your synthesis. Do not add any text after the JSON."
    )

    return "\n".join(parts)


async def _call_single_model(client, model_key: str, prompt: str) -> Dict:
    """Call a single Groq model and return its analysis text."""
    model_entry = GROQ_MODELS.get(model_key, GROQ_MODELS[DEFAULT_MODEL])
    groq_model_id = model_entry["id"]
    label = model_entry["label"]

    try:
        response = await client.chat.completions.create(
            model=groq_model_id,
            messages=[
                {
                    "role": "system",
                    "content": ANALYST_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        # Strip chart JSON from individual analyses (we only want it from synthesis)
        idx = content.rfind("CHART_JSON:")
        if idx != -1:
            content = content[:idx].strip()
        return {"model": model_key, "label": label, "analysis": content, "status": "success"}
    except Exception as e:
        logger.warning(f"Model {label} failed: {e}")
        return {"model": model_key, "label": label, "analysis": None, "status": "error", "message": str(e)}


async def generate_consensus_analysis(
    prediction: Dict,
    analysis: Optional[Dict],
    match_info: Dict,
) -> Dict:
    """
    Run all 3 Groq models in parallel, collect their analyses,
    then synthesise into a single consensus prediction.
    """
    import asyncio

    if not settings.GROQ_API_KEY:
        return {
            "status": "no_api_key",
            "ai_analysis": None,
            "message": "Groq API key not configured. Set GROQ_API_KEY in your .env file.",
        }

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

        # Build the data prompt (same for all models)
        prompt = _build_prompt(prediction, analysis or {}, match_info)

        # Phase 1: Run all 3 models in parallel
        logger.info("Consensus AI: launching all 3 models in parallel...")
        model_keys = list(GROQ_MODELS.keys())
        tasks = [_call_single_model(client, key, prompt) for key in model_keys]
        results = await asyncio.gather(*tasks)

        # Collect successful analyses
        individual_analyses = {}
        individual_summaries = []
        for r in results:
            if r["status"] == "success" and r["analysis"]:
                individual_analyses[r["model"]] = r["analysis"]
                individual_summaries.append({"model": r["label"], "status": "✅ Success"})
            else:
                individual_summaries.append({"model": r["label"], "status": f"❌ Failed: {r.get('message', 'unknown')}"})

        if len(individual_analyses) < 2:
            # Need at least 2 models for meaningful consensus
            return {
                "status": "error",
                "ai_analysis": None,
                "message": f"Only {len(individual_analyses)} model(s) responded. Need at least 2 for consensus.",
                "individual_results": individual_summaries,
            }

        # Phase 2: Synthesise using the strongest available model
        logger.info(f"Consensus AI: synthesising {len(individual_analyses)} analyses...")
        synthesis_prompt = _build_synthesis_prompt(individual_analyses, match_info)

        # Use GPT OSS 120B for synthesis if available, otherwise Llama 4
        synth_model = "openai/gpt-oss-120b"
        response = await client.chat.completions.create(
            model=synth_model,
            messages=[
                {
                    "role": "system",
                    "content": CONSENSUS_SYSTEM_PROMPT,
                },
                {"role": "user", "content": synthesis_prompt},
            ],
            max_tokens=2000,
            temperature=0.5,
        )

        content = response.choices[0].message.content

        # Extract chart data
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
                    logger.warning(f"Failed to parse consensus chart JSON: {parse_err}")

        total_tokens = sum(
            r.get("tokens", 0) for r in results
        )

        return {
            "status": "success",
            "ai_analysis": content,
            "chart_data": chart_data,
            "models_used": list(individual_analyses.keys()),
            "individual_results": individual_summaries,
            "synthesis_model": "GPT OSS 120B",
        }

    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        return {"status": "error", "ai_analysis": None, "message": "openai package not installed"}
    except Exception as e:
        logger.error(f"Consensus analysis failed: {e}")
        return {"status": "error", "ai_analysis": None, "message": str(e)}

