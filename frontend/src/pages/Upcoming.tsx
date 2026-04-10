import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchEvents, fetchEventLines, fetchEventBetfair, type ApiEvent } from "../lib/api";

const SPORTS = [
  { key: "", label: "All Sports" },
  { key: "aussierules_afl", label: "AFL" },
  { key: "rugbyleague_nrl", label: "NRL" },
  { key: "basketball_nba", label: "NBA" },
  { key: "americanfootball_nfl", label: "NFL" },
];

type Tab = "h2h" | "handicap" | "totals";

function EventRow({ event }: { event: ApiEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<Tab>("h2h");
  const navigate = useNavigate();

  const { data: linesData } = useQuery({
    queryKey: ["eventLines", event.id],
    queryFn: () => fetchEventLines(event.id),
    enabled: expanded,
    staleTime: 60_000,
  });

  const { data: betfairData } = useQuery({
    queryKey: ["eventBetfair", event.id],
    queryFn: () => fetchEventBetfair(event.id),
    enabled: expanded,
    staleTime: 60_000,
  });

  const layBySelection: Record<string, number> = {};
  betfairData?.runners.forEach((r) => { layBySelection[r.selection_name.toLowerCase()] = r.lay_price; });

  const filteredLines = (linesData?.lines ?? []).filter((l) => l.market_type === tab);

  return (
    <div className="border border-[#2e2e35] rounded-lg overflow-hidden">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#161618] transition-colors text-left">
        <div>
          <div className="text-sm text-zinc-400 mb-0.5">
            {new Date(event.commence_time).toLocaleString("en-AU", { timeZone: "Australia/Sydney" })} · {event.sport_key}
          </div>
          <div className="font-semibold text-zinc-200">{event.event_name}</div>
        </div>
        <span className="text-zinc-600 font-mono">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="border-t border-[#2e2e35] bg-[#0e0e10]">
          <div className="flex gap-1 px-4 pt-3">
            {(["h2h", "handicap", "totals"] as Tab[]).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`text-xs px-3 py-1.5 rounded transition-colors ${tab === t ? "bg-[#222226] text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}>
                {t === "h2h" ? "H2H" : t === "handicap" ? "Spread" : "Totals"}
              </button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full mt-2">
              <thead>
                <tr className="text-xs text-zinc-600 uppercase">
                  {["Bookmaker", "Line", "Odds", "Betfair LAY", "EV%", ""].map((h) => (
                    <th key={h} className="px-4 py-2 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredLines.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-4 text-center text-zinc-600 text-sm">No lines available</td></tr>
                ) : (
                  filteredLines.map((line, i) => {
                    const layPrice = layBySelection[line.selection.toLowerCase()] ?? null;
                    const fairProb = layPrice ? 1 / layPrice : null;
                    const ev = fairProb != null ? (fairProb * (line.odds - 1) - (1 - fairProb)) * 100 : null;
                    const evColor = ev == null ? "text-zinc-600" : ev > 2 ? "text-green-400" : ev > 0 ? "text-amber-400" : "text-zinc-500";
                    return (
                      <tr key={i} className="border-b border-[#1e1e22] hover:bg-[#161618]">
                        <td className="px-4 py-2 text-sm text-zinc-300">{line.bookmaker}</td>
                        <td className="px-4 py-2 font-mono text-sm text-zinc-300">{line.line != null ? String(line.line) : "—"}</td>
                        <td className="px-4 py-2 font-mono text-sm text-zinc-200">{line.odds.toFixed(2)}</td>
                        <td className="px-4 py-2 font-mono text-sm text-zinc-400">{layPrice != null ? layPrice.toFixed(2) : "—"}</td>
                        <td className={`px-4 py-2 font-mono text-sm ${evColor}`}>{ev != null ? `${ev >= 0 ? "+" : ""}${ev.toFixed(2)}%` : "—"}</td>
                        <td className="px-4 py-2">
                          <button className="text-xs text-zinc-400 hover:text-zinc-200 border border-[#2e2e35] hover:border-zinc-500 rounded px-2 py-1 transition-colors">Track</button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3">
            <button onClick={() => navigate(`/bets/add?event=${event.id}&sport=${event.sport_key}`)}
              className="text-xs px-3 py-2 rounded border border-[#2e2e35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors">
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

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["events", sport],
    queryFn: () => fetchEvents(sport || undefined, 7),
    staleTime: 120_000,
  });

  const filtered = events.filter((e) => e.event_name.toLowerCase().includes(search.toLowerCase()) && e.status !== "completed");

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-lg font-semibold text-zinc-200 mb-6">Upcoming Events</h1>
      <div className="flex gap-3 mb-6">
        <select className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none" value={sport} onChange={(e) => setSport(e.target.value)}>
          {SPORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <input className="flex-1 bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none placeholder-zinc-600"
          placeholder="Search events…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      {isLoading && <div className="text-zinc-500 text-sm">Loading…</div>}
      {!isLoading && filtered.length === 0 && <div className="text-center py-16 text-zinc-600 text-sm">No upcoming events</div>}
      <div className="flex flex-col gap-3">
        {filtered.map((event) => <EventRow key={event.id} event={event} />)}
      </div>
    </div>
  );
}
