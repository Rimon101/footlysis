import sys
import os
import asyncio
import traceback
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from app.models.models import Match, Team
from app.services.prediction_engine import predict_match
from sqlalchemy import select

async def verify_engine():
    db = AsyncSessionLocal()
    
    try:
        # Fetch one match to test
        stmt = select(Match).where(Match.status == "finished").limit(1)
        result = await db.execute(stmt)
        m = result.scalar_one_or_none()
        
        if not m:
            print("No finished matches found.")
            return

        home_team = await db.get(Team, m.home_team_id)
        away_team = await db.get(Team, m.away_team_id)
        
        print(f"--- Phase 2 Engine Verification ---")
        print(f"Match: {home_team.name} vs {away_team.name}")
        
        # Test the prediction call (Sync call)
        prediction = predict_match(
            home_team_name=home_team.name,
            away_team_name=away_team.name,
            home_recent_matches=[], 
            away_recent_matches=[],
            home_elo=home_team.elo_rating,
            away_elo=away_team.elo_rating,
            home_players=[{"name": "Missing Star", "is_injured": True, "xg_per90": 0.4, "xa_per90": 0.2}], 
            away_players=[],
            home_stats={"ppda": 8.5}, # High press
            away_stats={"ppda": 14.0},
            market_odds={"home": 2.1, "draw": 3.4, "away": 3.6}
        )
        
        print(f"Probabilities: H:{prediction['prob_home_win']:.4f} D:{prediction['prob_draw']:.4f} A:{prediction['prob_away_win']:.4f}")
        print(f"Confidence: {prediction['confidence']}%")
        print(f"Squad Impact Home: {prediction.get('squad_impact_home')}")
        print(f"Model ID: {prediction['model_used']}")
        print("--- VERIFICATION SUCCESSFUL ---")

    except Exception as e:
        print(f"Verification failed with error: {e}")
        traceback.print_exc()
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(verify_engine())
