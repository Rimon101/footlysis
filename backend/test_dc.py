import time
import random
import logging
logging.basicConfig(level=logging.INFO)

from app.services.dixon_coles import fit_dixon_coles

def main():
    teams = [f"Team_{i}" for i in range(20)]
    results = []
    
    # Generate 200 random matches
    for _ in range(200):
        t1, t2 = random.sample(teams, 2)
        results.append({
            "home_team": t1,
            "away_team": t2,
            "home_goals": random.randint(0, 4),
            "away_goals": random.randint(0, 3),
            "days_ago": random.randint(0, 365)
        })

    print(f"Starting fitting for {len(teams)} teams and {len(results)} matches")
    t0 = time.time()
    fit = fit_dixon_coles(results)
    print(f"Fitting took {time.time() - t0:.2f} seconds")

if __name__ == "__main__":
    main()
