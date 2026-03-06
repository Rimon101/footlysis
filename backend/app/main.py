from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import matches, teams, players, predictions, betting, leagues, data, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Footlysis API",
    description="Professional football analytics and match prediction platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(teams.router)
app.include_router(players.router)
app.include_router(predictions.router)
app.include_router(betting.router)
app.include_router(leagues.router)
app.include_router(data.router)
app.include_router(dashboard.router)


@app.get("/")
async def root():
    return {
        "app": "Footlysis",
        "version": "1.0.0",
        "description": "Professional Football Analytics & Prediction Platform",
        "docs": "/docs",
        "endpoints": [
            "/matches", "/teams", "/players", "/predictions",
            "/betting", "/leagues", "/data", "/dashboard"
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
