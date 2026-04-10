from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.session import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sport_key: Mapped[str] = mapped_column(String, nullable=False)
    sport_title: Mapped[str] = mapped_column(String, nullable=False)
    commence_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    home_team: Mapped[str] = mapped_column(String, nullable=False)
    away_team: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    bets: Mapped[list["TrackedBet"]] = relationship("TrackedBet", back_populates="event")
    odds_snapshots: Mapped[list["OddsSnapshot"]] = relationship("OddsSnapshot", back_populates="event")


class TrackedBet(Base):
    __tablename__ = "tracked_bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.id"), nullable=False)
    sport_key: Mapped[str] = mapped_column(String, nullable=False)
    event_name: Mapped[str] = mapped_column(String, nullable=False)
    commence_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    selection: Mapped[str] = mapped_column(String, nullable=False)
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    odds_taken: Mapped[float] = mapped_column(Float, nullable=False)
    stake: Mapped[float] = mapped_column(Float, nullable=False)
    bookmaker: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")
    settle_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="bets")
    closing_line: Mapped[Optional["ClosingLine"]] = relationship(
        "ClosingLine", back_populates="bet", uselist=False
    )


class ClosingLine(Base):
    __tablename__ = "closing_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bet_id: Mapped[int] = mapped_column(Integer, ForeignKey("tracked_bets.id"), nullable=False)

    betfair_lay_at_bet: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    betfair_lay_at_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    odds_clv_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beat_closing_odds: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    line_at_open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line_at_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line_clv_pts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beat_closing_line: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    capture_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    bet: Mapped["TrackedBet"] = relationship("TrackedBet", back_populates="closing_line")


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.id"), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String, nullable=False)
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    selection: Mapped[str] = mapped_column(String, nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    event: Mapped["Event"] = relationship("Event", back_populates="odds_snapshots")


class BetfairSnapshot(Base):
    __tablename__ = "betfair_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    selection_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    selection_name: Mapped[str] = mapped_column(String, nullable=False)
    market_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
