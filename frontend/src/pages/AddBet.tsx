import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchEvents, createBet, type ApiEvent } from "../lib/api";

const SPORTS = [
  { key: "aussierules_afl", label: "AFL" },
  { key: "rugbyleague_nrl", label: "NRL" },
  { key: "basketball_nba", label: "NBA" },
  { key: "americanfootball_nfl", label: "NFL" },
];
const BOOKMAKERS = ["tab", "sportsbet", "neds", "pointsbet", "bet365", "betfair"];
type MarketType = "h2h" | "handicap" | "totals";

export default function AddBet() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [sport, setSport] = useState("");
  const [eventId, setEventId] = useState("");
  const [eventSearch, setEventSearch] = useState("");
  const [marketType, setMarketType] = useState<MarketType>("h2h");
  const [selection, setSelection] = useState("");
  const [line, setLine] = useState("");
  const [side, setSide] = useState("");
  const [odds, setOdds] = useState("");
  const [stake, setStake] = useState("");
  const [bookmaker, setBookmaker] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["events", sport],
    queryFn: () => fetchEvents(sport, 7),
    enabled: !!sport,
  });

  const selectedEvent = events.find((e) => e.id === eventId);
  const filteredEvents = events.filter((e) =>
    e.event_name.toLowerCase().includes(eventSearch.toLowerCase())
  );

  const { mutate: submit, isPending } = useMutation({
    mutationFn: createBet,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bets"] }); navigate("/bets/open"); },
  });

  function selectionOptions(event: ApiEvent | undefined, mt: MarketType): string[] {
    if (!event) return [];
    if (mt === "h2h" || mt === "handicap") return [event.home_team, event.away_team];
    return ["Over", "Under"];
  }

  function sideForSelection(sel: string, event: ApiEvent | undefined): string {
    if (!event) return "";
    if (sel === "Over") return "over";
    if (sel === "Under") return "under";
    if (sel === event.home_team) return "home";
    if (sel === event.away_team) return "away";
    return "";
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!sport) errs.sport = "Select a sport";
    if (!eventId) errs.event = "Select an event";
    if (!selection) errs.selection = "Select a selection";
    if (!bookmaker) errs.bookmaker = "Select a bookmaker";
    const oddsNum = parseFloat(odds);
    if (isNaN(oddsNum) || oddsNum <= 1.0) errs.odds = "Odds must be > 1.0";
    const stakeNum = parseFloat(stake);
    if (isNaN(stakeNum) || stakeNum <= 0) errs.stake = "Stake must be > 0";
    if (marketType !== "h2h" && !line) errs.line = "Enter a line";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    submit({
      event_id: eventId,
      sport_key: sport,
      selection,
      market_type: marketType,
      line: marketType !== "h2h" ? parseFloat(line) : null,
      side,
      odds_taken: parseFloat(odds),
      stake: parseFloat(stake),
      bookmaker,
      notes: notes || undefined,
    });
  }

  const sel = "w-full bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500";
  const inp = `${sel} font-mono`;
  const err = "text-xs text-red-400 mt-1";
  const lbl = "block text-xs text-zinc-500 uppercase tracking-wider mb-1.5";

  return (
    <div className="p-6 max-w-xl">
      <h1 className="text-lg font-semibold text-zinc-200 mb-6">Add Bet</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div>
          <label className={lbl}>Sport</label>
          <select className={sel} value={sport} onChange={(e) => { setSport(e.target.value); setEventId(""); setEventSearch(""); setSelection(""); }}>
            <option value="">Select sport…</option>
            {SPORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          {errors.sport && <div className={err}>{errors.sport}</div>}
        </div>

        {sport && (
          <div>
            <label className={lbl}>Event</label>
            <input className={inp} placeholder="Search events…" value={eventSearch} onChange={(e) => setEventSearch(e.target.value)} />
            {eventsLoading ? (
              <div className="text-xs text-zinc-500 mt-2">Loading events…</div>
            ) : (
              <select className={`${sel} mt-2`} value={eventId} onChange={(e) => { setEventId(e.target.value); setSelection(""); setSide(""); }} size={Math.min(filteredEvents.length + 1, 6)}>
                <option value="">Select event…</option>
                {filteredEvents.map((ev) => (
                  <option key={ev.id} value={ev.id}>{ev.event_name} — {new Date(ev.commence_time).toLocaleDateString("en-AU", { timeZone: "Australia/Sydney" })}</option>
                ))}
              </select>
            )}
            {errors.event && <div className={err}>{errors.event}</div>}
          </div>
        )}

        {eventId && (
          <div>
            <label className={lbl}>Market Type</label>
            <div className="flex gap-2">
              {(["h2h", "handicap", "totals"] as MarketType[]).map((mt) => (
                <button key={mt} type="button" onClick={() => { setMarketType(mt); setSelection(""); setSide(""); setLine(""); }}
                  className={`flex-1 py-2 text-sm rounded border transition-colors ${marketType === mt ? "border-zinc-500 bg-[#222226] text-zinc-200" : "border-[#2e2e35] text-zinc-500 hover:border-zinc-600"}`}>
                  {mt === "h2h" ? "H2H" : mt === "handicap" ? "Handicap" : "Totals"}
                </button>
              ))}
            </div>
          </div>
        )}

        {eventId && (
          <div>
            <label className={lbl}>Selection</label>
            <select className={sel} value={selection} onChange={(e) => { setSelection(e.target.value); setSide(sideForSelection(e.target.value, selectedEvent)); }}>
              <option value="">Select…</option>
              {selectionOptions(selectedEvent, marketType).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {errors.selection && <div className={err}>{errors.selection}</div>}
          </div>
        )}

        {eventId && marketType !== "h2h" && (
          <div>
            <label className={lbl}>Line {marketType === "totals" ? "(total points)" : "(handicap)"}</label>
            <input className={inp} type="number" step="0.5" placeholder={marketType === "totals" ? "e.g. 160.5" : "e.g. -3.5"} value={line} onChange={(e) => setLine(e.target.value)} />
            {errors.line && <div className={err}>{errors.line}</div>}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={lbl}>Odds (decimal)</label>
            <input className={inp} type="number" step="0.01" min="1.01" placeholder="e.g. 1.95" value={odds} onChange={(e) => setOdds(e.target.value)} />
            {errors.odds && <div className={err}>{errors.odds}</div>}
          </div>
          <div>
            <label className={lbl}>Stake ($)</label>
            <input className={inp} type="number" step="any" min="0.01" placeholder="e.g. 100" value={stake} onChange={(e) => setStake(e.target.value)} />
            {errors.stake && <div className={err}>{errors.stake}</div>}
          </div>
        </div>

        <div>
          <label className={lbl}>Bookmaker</label>
          <select className={sel} value={bookmaker} onChange={(e) => setBookmaker(e.target.value)}>
            <option value="">Select bookmaker…</option>
            {BOOKMAKERS.map((bm) => <option key={bm} value={bm}>{bm}</option>)}
          </select>
          {errors.bookmaker && <div className={err}>{errors.bookmaker}</div>}
        </div>

        <div>
          <label className={lbl}>Notes (optional)</label>
          <textarea className={`${inp} resize-none h-16`} placeholder="Any notes…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        <button type="submit" disabled={isPending}
          className="w-full py-3 rounded bg-zinc-200 text-zinc-900 font-semibold text-sm hover:bg-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          {isPending ? "Logging bet…" : "Log Bet"}
        </button>
      </form>
    </div>
  );
}
