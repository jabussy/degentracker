import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  fetchEvents,
  fetchEventLines,
  type ApiEvent,
  type EventLinesH2H,
  type EventLinesSpread,
  type EventLinesTotals,
  type EventLines,
} from "../lib/api";

const SPORTS = [
  { key: "", label: "All Sports" },
  { key: "aussierules_afl", label: "AFL" },
  { key: "rugbyleague_nrl", label: "NRL" },
  { key: "basketball_nba", label: "NBA" },
  { key: "americanfootball_nfl", label: "NFL" },
];

type Tab = "h2h" | "spreads" | "totals";

function calcEV(odds: number, fairProb: number): number {
  return (fairProb * (odds - 1)) - (1 - fairProb);
}

function evColor(ev: number | null): string {
  if (ev == null) return "text-zinc-600";
  if (ev > 0.02) return "text-green-400";
  if (ev > 0) return "text-amber-400";
  return "text-zinc-500";
}

function fmtEV(ev: number | null): string {
  if (ev == null) return "—";
  const pct = ev * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function H2HTable({
  rows,
  betfairLay,
  betfairFairProb,
  event,
  onTrack,
}: {
  rows: EventLinesH2H[];
  betfairLay: EventLines["betfair_lay"];
  betfairFairProb: EventLines["betfair_fair_prob"];
  event: ApiEvent;
  onTrack: (opts: { bookmaker_key: string; bookmaker: string; selection: string; market_type: string; odds: number }) => void;
}) {
  if (rows.length === 0) {
    return <div className="py-6 text-center text-zinc-600 text-sm">No H2H lines available</div>;
  }
  const homeLayPrice = betfairLay?.home ?? null;
  const awayLayPrice = betfairLay?.away ?? null;
  // Prefer the power-devigged fair prob (sums to 1 across the market); fall back
  // to the raw 1/lay implied prob when only one side of the exchange is captured.
  const homeFairProb = betfairFairProb?.home ?? (homeLayPrice ? 1 / homeLayPrice : null);
  const awayFairProb = betfairFairProb?.away ?? (awayLayPrice ? 1 / awayLayPrice : null);

  return (
    <table className="w-full">
      <thead>
        <tr className="text-xs text-zinc-600 uppercase">
          <th className="px-4 py-2 text-left">Bookmaker</th>
          <th className="px-4 py-2 text-left">{event.home_team}</th>
          <th className="px-4 py-2 text-left">{event.away_team}</th>
          <th className="px-4 py-2 text-left">Betfair LAY (H)</th>
          <th className="px-4 py-2 text-left">EV% (H)</th>
          <th className="px-4 py-2 text-left">EV% (A)</th>
          <th className="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const homeEV = homeFairProb != null && row.home_odds ? calcEV(row.home_odds, homeFairProb) : null;
          const awayEV = awayFairProb != null && row.away_odds ? calcEV(row.away_odds, awayFairProb) : null;
          return (
            <tr key={i} className="border-b border-[#1e1e22] hover:bg-[#161618]">
              <td className="px-4 py-2 text-sm text-zinc-300">{row.bookmaker}</td>
              <td
                className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
                onClick={() => row.home_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: event.home_team, market_type: "h2h", odds: row.home_odds })}
              >
                {row.home_odds?.toFixed(2) ?? "—"}
              </td>
              <td
                className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
                onClick={() => row.away_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: event.away_team, market_type: "h2h", odds: row.away_odds })}
              >
                {row.away_odds?.toFixed(2) ?? "—"}
              </td>
              <td className="px-4 py-2 font-mono text-sm text-zinc-400">
                {homeLayPrice != null ? homeLayPrice.toFixed(2) : "—"}
              </td>
              <td className={`px-4 py-2 font-mono text-sm ${evColor(homeEV)}`}>{fmtEV(homeEV)}</td>
              <td className={`px-4 py-2 font-mono text-sm ${evColor(awayEV)}`}>{fmtEV(awayEV)}</td>
              <td className="px-4 py-2">
                <button
                  className="text-xs text-zinc-400 hover:text-zinc-200 border border-[#2e2e35] hover:border-zinc-500 rounded px-2 py-1 transition-colors"
                  onClick={() => onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: event.home_team, market_type: "h2h", odds: row.home_odds ?? 0 })}
                >
                  Track
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SpreadTable({
  rows,
  betfairLay,
  onTrack,
}: {
  rows: EventLinesSpread[];
  betfairLay: EventLines["betfair_lay"];
  onTrack: (opts: { bookmaker_key: string; bookmaker: string; selection: string; market_type: string; odds: number; line?: number }) => void;
}) {
  if (rows.length === 0) {
    return <div className="py-6 text-center text-zinc-600 text-sm">No spread lines available for this event</div>;
  }
  const homeLayPrice = betfairLay?.home ?? null;

  return (
    <table className="w-full">
      <thead>
        <tr className="text-xs text-zinc-600 uppercase">
          <th className="px-4 py-2 text-left">Bookmaker</th>
          <th className="px-4 py-2 text-left">Home Line</th>
          <th className="px-4 py-2 text-left">Home Odds</th>
          <th className="px-4 py-2 text-left">Away Line</th>
          <th className="px-4 py-2 text-left">Away Odds</th>
          <th className="px-4 py-2 text-left">Betfair LAY</th>
          <th className="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-[#1e1e22] hover:bg-[#161618]">
            <td className="px-4 py-2 text-sm text-zinc-300">{row.bookmaker}</td>
            <td className="px-4 py-2 font-mono text-sm text-zinc-300">
              {row.home_line != null ? (row.home_line > 0 ? `+${row.home_line}` : String(row.home_line)) : "—"}
            </td>
            <td
              className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
              onClick={() => row.home_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: row.home_team, market_type: "handicap", odds: row.home_odds, line: row.home_line ?? undefined })}
            >
              {row.home_odds?.toFixed(2) ?? "—"}
            </td>
            <td className="px-4 py-2 font-mono text-sm text-zinc-300">
              {row.away_line != null ? (row.away_line > 0 ? `+${row.away_line}` : String(row.away_line)) : "—"}
            </td>
            <td
              className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
              onClick={() => row.away_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: row.away_team, market_type: "handicap", odds: row.away_odds, line: row.away_line ?? undefined })}
            >
              {row.away_odds?.toFixed(2) ?? "—"}
            </td>
            <td className="px-4 py-2 font-mono text-sm text-zinc-400">
              {homeLayPrice != null ? homeLayPrice.toFixed(2) : "—"}
            </td>
            <td className="px-4 py-2">
              <button
                className="text-xs text-zinc-400 hover:text-zinc-200 border border-[#2e2e35] hover:border-zinc-500 rounded px-2 py-1 transition-colors"
                onClick={() => row.home_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: row.home_team, market_type: "handicap", odds: row.home_odds, line: row.home_line ?? undefined })}
              >
                Track
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TotalsTable({
  rows,
  onTrack,
}: {
  rows: EventLinesTotals[];
  onTrack: (opts: { bookmaker_key: string; bookmaker: string; selection: string; market_type: string; odds: number; line?: number }) => void;
}) {
  if (rows.length === 0) {
    return <div className="py-6 text-center text-zinc-600 text-sm">No totals lines available for this event</div>;
  }
  return (
    <table className="w-full">
      <thead>
        <tr className="text-xs text-zinc-600 uppercase">
          <th className="px-4 py-2 text-left">Bookmaker</th>
          <th className="px-4 py-2 text-left">Line</th>
          <th className="px-4 py-2 text-left">Over</th>
          <th className="px-4 py-2 text-left">Under</th>
          <th className="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-[#1e1e22] hover:bg-[#161618]">
            <td className="px-4 py-2 text-sm text-zinc-300">{row.bookmaker}</td>
            <td className="px-4 py-2 font-mono text-sm text-zinc-300">{row.line ?? "—"}</td>
            <td
              className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
              onClick={() => row.over_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: "Over", market_type: "totals", odds: row.over_odds, line: row.line ?? undefined })}
            >
              {row.over_odds?.toFixed(2) ?? "—"}
            </td>
            <td
              className="px-4 py-2 font-mono text-sm text-zinc-200 cursor-pointer hover:text-white"
              onClick={() => row.under_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: "Under", market_type: "totals", odds: row.under_odds, line: row.line ?? undefined })}
            >
              {row.under_odds?.toFixed(2) ?? "—"}
            </td>
            <td className="px-4 py-2">
              <button
                className="text-xs text-zinc-400 hover:text-zinc-200 border border-[#2e2e35] hover:border-zinc-500 rounded px-2 py-1 transition-colors"
                onClick={() => row.over_odds && onTrack({ bookmaker_key: row.bookmaker_key, bookmaker: row.bookmaker, selection: "Over", market_type: "totals", odds: row.over_odds, line: row.line ?? undefined })}
              >
                Track
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EventRow({ event }: { event: ApiEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<Tab>("h2h");
  const navigate = useNavigate();

  const {
    data: linesData,
    isLoading: linesLoading,
    isError: linesError,
  } = useQuery({
    queryKey: ["event-lines", event.id],
    queryFn: () => fetchEventLines(event.id),
    enabled: expanded,
    staleTime: 2 * 60 * 1000,
  });

  function navigateToAddBet(opts?: {
    bookmaker_key?: string;
    bookmaker?: string;
    selection?: string;
    market_type?: string;
    odds?: number;
    line?: number;
  }) {
    navigate("/bets/add", {
      state: {
        event_id: event.id,
        event_name: event.event_name,
        sport_key: event.sport_key,
        commence_time: event.commence_time,
        ...(opts?.bookmaker && { bookmaker: opts.bookmaker_key }),
        ...(opts?.selection && { selection: opts.selection }),
        ...(opts?.market_type && { market_type: opts.market_type }),
        ...(opts?.odds && { odds_taken: opts.odds }),
        ...(opts?.line != null && { line: opts.line }),
      },
    });
  }

  return (
    <div className="border border-[#2e2e35] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#161618] transition-colors text-left"
      >
        <div>
          <div className="text-sm text-zinc-400 mb-0.5">
            {new Date(event.commence_time).toLocaleString("en-AU", { timeZone: "Australia/Sydney" })} ·{" "}
            {event.sport_key}
          </div>
          <div className="font-semibold text-zinc-200">{event.event_name}</div>
        </div>
        <span className="text-zinc-600 font-mono">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="border-t border-[#2e2e35] bg-[#0e0e10]">
          <div className="flex gap-1 px-4 pt-3">
            {(["h2h", "spreads", "totals"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`text-xs px-3 py-1.5 rounded transition-colors ${
                  tab === t
                    ? "bg-[#222226] text-zinc-200"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {t === "h2h" ? "H2H" : t === "spreads" ? "Spread" : "Totals"}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto mt-2">
            {linesLoading && (
              <div className="py-6 text-center text-zinc-500 text-sm">Loading lines…</div>
            )}
            {linesError && (
              <div className="py-6 text-center text-red-400 text-sm">
                Failed to load lines — check the backend.
              </div>
            )}
            {!linesLoading && !linesError && linesData && (
              <>
                {tab === "h2h" && (
                  <H2HTable
                    rows={linesData.h2h}
                    betfairLay={linesData.betfair_lay}
                    betfairFairProb={linesData.betfair_fair_prob}
                    event={event}
                    onTrack={(opts) => navigateToAddBet(opts)}
                  />
                )}
                {tab === "spreads" && (
                  <SpreadTable
                    rows={linesData.spreads}
                    betfairLay={linesData.betfair_lay}
                    onTrack={(opts) => navigateToAddBet(opts)}
                  />
                )}
                {tab === "totals" && (
                  <TotalsTable
                    rows={linesData.totals}
                    onTrack={(opts) => navigateToAddBet(opts)}
                  />
                )}
              </>
            )}
          </div>

          <div className="px-4 py-3">
            <button
              onClick={() => navigateToAddBet()}
              className="text-xs px-3 py-2 rounded border border-[#2e2e35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors"
            >
              + Track a bet on this event
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Upcoming() {
  const [sport, setSport] = useState("");
  const [search, setSearch] = useState("");

  const {
    data: events = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["events", sport],
    queryFn: () => fetchEvents(sport || undefined, 7),
    staleTime: 120_000,
  });

  const filtered = events.filter(
    (e) =>
      e.event_name.toLowerCase().includes(search.toLowerCase()) &&
      e.status !== "completed"
  );

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-lg font-semibold text-zinc-200 mb-6">Upcoming Events</h1>
      <div className="flex gap-3 mb-6">
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={sport}
          onChange={(e) => setSport(e.target.value)}
        >
          {SPORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
        <input
          className="flex-1 bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none placeholder-zinc-600"
          placeholder="Search events…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading && <div className="text-zinc-500 text-sm">Loading…</div>}
      {isError && (
        <div className="text-red-400 text-sm">Failed to load events — check the backend is running.</div>
      )}
      {!isLoading && !isError && filtered.length === 0 && (
        <div className="text-center py-16 text-zinc-600 text-sm">No upcoming events</div>
      )}

      <div className="flex flex-col gap-3">
        {filtered.map((event) => (
          <EventRow key={event.id} event={event} />
        ))}
      </div>
    </div>
  );
}
