# Footlysis — Football Analytics Platform

A full-stack football analytics web app with xG models, Poisson/Dixon-Coles predictions, Kelly Criterion bankroll management, and live data ingestion from free sources.

---

## Features

| Area | Coverage |
|---|---|
| Historical Results | 4 seasons, 9 leagues, Football-Data.co.uk |
| xG Metrics | Understat xG/xA per match and player |
| Prediction Models | Poisson Distribution + Dixon-Coles (MLE + time-decay) |
| Elo Ratings | 1500 base, K=32, 100pt home advantage |
| Betting Markets | H/D/A · Over/Under 2.5 · BTTS · Correct Score |
| Kelly Criterion | Quarter-Kelly default, edge %, overround analysis |
| Player Data | xG/90, xA/90, injury/suspension flags |
| Standings | Live tables with CS% and BTTS% analytics |

---

## Quick Start — Manual

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

### 1. Database
```bash
createdb footlysis
```

### 2. Backend
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\python.exe -m pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL if needed
venv\Scripts\python.exe -m uvicorn app.main:app --reload

# macOS / Linux
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The database tables are created automatically on first startup.  
API docs → http://localhost:8000/docs

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

App → http://localhost:5173

---

## Quick Start — Docker

```bash
docker compose up --build
```

- Frontend → http://localhost:5173  
- Backend API → http://localhost:8000  
- Swagger docs → http://localhost:8000/docs

---

## Data Workflow

1. **Open Data Manager** (sidebar → Data icon)
2. Select a league and click **Start Scraping** — fetches 4 seasons of results + xG
3. Click **Recalculate Stats** — updates form, rolling averages, CS%, BTTS%
4. Click **Recalculate Elo** — replays all matches to update Elo ratings
5. Go to **Matches** → pick an upcoming match → click **Generate Prediction**
6. Use the **Betting** page to run Kelly calculations and scan for value bets

---

## Project Structure

```
Footlysis/
├── backend/
│   ├── app/
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── routers/       # FastAPI endpoint routers
│   │   └── services/
│   │       ├── poisson_model.py    # Poisson distribution
│   │       ├── dixon_coles.py      # Dixon-Coles + Elo
│   │       ├── kelly_criterion.py  # Bankroll management
│   │       ├── form_calculator.py  # Rolling form & momentum
│   │       ├── data_scraper.py     # Free data ingestion
│   │       └── prediction_engine.py # Orchestrator
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # Layout, UI primitives, PredictionCard
│   │   ├── pages/         # 10 route pages
│   │   └── services/      # Axios API layer
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Models

### Dixon-Coles
- Maximum Likelihood Estimation via `scipy.optimize.minimize` (SLSQP)
- Time-decay weighting: `exp(-ξ·days)` where ξ = 0.0018
- Low-score rho correction (τ adjustment for 0-0, 1-0, 0-1, 1-1)
- Blended 75% Dixon-Coles / 25% Elo in final prediction

### Poisson
- Simple independent Poisson with attack/defence strength estimates
- Used as fallback when Dixon-Coles fitting fails

### Kelly Criterion
- `f = (bp - q) / b`
- Default fraction: 0.25 (Quarter Kelly)
- Edge threshold: 2% minimum to flag as value bet

---

## Supported Leagues

| League | Code |
|---|---|
| Premier League | E0 |
| La Liga | SP1 |
| Bundesliga | D1 |
| Serie A | I1 |
| Ligue 1 | F1 |
| Eredivisie | N1 |
| Primeira Liga | P1 |
| Scottish Prem | SC0 |
| Championship | E1 |
