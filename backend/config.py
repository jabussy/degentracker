from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ODDS_API_KEY: str = ""
    BETFAIR_USERNAME: str = ""
    BETFAIR_PASSWORD: str = ""
    BETFAIR_APP_KEY: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./bets.db"
    TRACKED_BOOKMAKERS: List[str] = ["betfair", "tab", "sportsbet", "neds", "pointsbet", "bet365"]
    SPORTS: List[str] = [
        "aussierules_afl",
        "rugbyleague_nrl",
        "americanfootball_nfl",
        "basketball_nba",
    ]
    CLOSING_LINE_WINDOW_MINUTES: int = 5
    CASHOUT_EDGE_THRESHOLD: float = 0.03
    BETFAIR_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
