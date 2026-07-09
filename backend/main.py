import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.session import init_db
from backend.routers import events, bets, stats, ev
from backend.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.config import settings as _settings
    key_prefix = _settings.ODDS_API_KEY[:4] if _settings.ODDS_API_KEY else "<not set>"
    logger.info("Starting up — initialising DB (ODDS_API_KEY prefix: %s...)", key_prefix)
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down")


app = FastAPI(title="Bet Tracker API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(bets.router)
app.include_router(stats.router)
app.include_router(ev.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
