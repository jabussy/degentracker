import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchEVOpportunities, scrapeBet365, scrapeBetfair, type EVOpportunity } from "../lib/api";

const SPORTS = [
  { key: "", label: "All Sports" },
  { key: "aussierules_afl", label: "AFL" },
  { key: "rugbyleague_nrl", label: "NRL" },
  { key: "basketball_nba", label: "NBA" },
  { key: "americanfootball_nfl", label: "NFL" },
];

const MARKETS = [
  { key: "", label: "All Markets" },
  { key: "h2h", label: "H2H" },
  { key: "handicap", label: "Spread" },
  { key: "totals", label: "Totals" },
];

const MIN_EV_OPTIONS = [
  { value: -100, label: "Any EV" },
  { value: 0, label: "EV > 0%" },
  { value: 1, label: "EV > 1%" },
  { value: 2, label: "EV > 2%" },
  { value: 3, label: "EV > 3%" },
  { value: 5, label: "EV > 5%" },
];

const DAYS_OPTIONS = [
  { value: 1, label: "Next 24h" },
  { value: 3, label: "Next 3 days" },
  { value: 7, label: "Next 7 days" },
];

function evColor(ev: number | null): string {
  if (ev == null) return "text-zinc-600";
  if (ev > 3) return "text-green-300 font-semibold";
  if (ev > 0) return "text-green-400";
  if (ev > -2) return "text-amber-400";
  return "text-zinc-500";
}

function fmtPct(v: number | null): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtMarket(o: EVOpportunity): string {
  if (o.market_type === "h2h") return "H2H";
  const line = o.line != null ? (o.line > 0 ? `+${o.line}` : String(o.line)) : "";
  if (o.market_type === "handicap") return `Spread ${line}`;
  return `Total ${o.selection === "Over" ? "o" : "u"}${o.line ?? ""}`;
}

function fmtKickoff(iso: string): string {
  return new Date(iso + "Z").toLocaleString("en-AU", {
    timeZone: "Australia/Sydney",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    day: "numeric",
    month: "short",
  });
}

export default function FindEV() {
  const [sport, setSport] = useState("");
  const [market, setMarket] = useState("");
  const [bookmaker, setBookmaker] = useState("");
  const [minEV, setMinEV] = useState(0);
  const [days, setDays] = useState(3);
  const [search, setSearch] = useState("");
  const [pricedOnly, setPricedOnly] = useState(true);

  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["ev", sport, days],
    queryFn: () => fetchEVOpportunities(sport || undefined, days),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });

  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null);
  const { mutate: runBet365Scan, isPending: scraping } = useMutation({
    mutationFn: scrapeBet365,
    onSuccess: (res) => {
      const fixtureCount = Object.values(res.fixtures).reduce((a, b) => a + b, 0);
      setScrapeMsg(
        `bet365: ${fixtureCount} fixtures scraped, ${res.snapshots} prices stored` +
          (res.unmatched.length ? `, ${res.unmatched.length} unmatched` : "")
      );
      qc.invalidateQueries({ queryKey: ["ev"] });
    },
    onError: (err: Error) => setScrapeMsg(`bet365 scrape failed: ${err.message}`),
  });
  const { mutate: runBetfairScan, isPending: scrapingBetfair } = useMutation({
    mutationFn: scrapeBetfair,
    onSuccess: (res) => {
      const fixtureCount = Object.values(res.fixtures).reduce((a, b) => a + b, 0);
      setScrapeMsg(
        `Betfair: ${fixtureCount} fixtures scraped, ${res.snapshots} prices stored` +
          (res.unmatched.length ? `, ${res.unmatched.length} unmatched` : "")
      );
      qc.invalidateQueries({ queryKey: ["ev"] });
    },
    onError: (err: Error) => setScrapeMsg(`Betfair scrape failed: ${err.message}`),
  });

  const all = data?.opportunities ?? [];

  const bookmakers = useMemo(
    () => [...new Set(all.map((o) => o.bookmaker))].sort(),
    [all]
  );

  const rows = useMemo(() => {
    return all.filter((o) => {
      if (pricedOnly && o.ev_pct == null) return false;
      if (market && o.market_type !== market) return false;
      if (bookmaker && o.bookmaker !== bookmaker) return false;
      if (o.ev_pct != null && o.ev_pct < minEV) return false;
      if (!pricedOnly && o.ev_pct == null && minEV > -100) return false;
      if (
        search &&
        !o.event_name.toLowerCase().includes(search.toLowerCase()) &&
        !o.selection.toLowerCase().includes(search.toLowerCase())
      )
        return false;
      return true;
    });
  }, [all, market, bookmaker, minEV, search, pricedOnly]);

  const positiveCount = all.filter((o) => (o.ev_pct ?? -1) > 0).length;

  function track(o: EVOpportunity) {
    navigate("/bets/add", {
      state: {
        event_id: o.event_id,
        event_name: o.event_name,
        sport_key: o.sport_key,
        commence_time: o.commence_time,
        bookmaker: o.bookmaker,
        selection: o.selection,
        market_type: o.market_type,
        odds_taken: o.odds,
        ...(o.line != null && { line: o.line }),
      },
    });
  }

  return (
    <div className="p-6 max-w-7xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-lg font-semibold text-zinc-200">Find EV</h1>
        <div className="flex items-center gap-3">
          {dataUpdatedAt > 0 && (
            <span className="text-xs text-zinc-600 font-mono">
              updated {new Date(dataUpdatedAt).toLocaleTimeString("en-AU", { timeZone: "Australia/Sydney" })}
            </span>
          )}
          <button
            onClick={() => runBetfairScan()}
            disabled={scrapingBetfair}
            title="Scrapes the Betfair Exchange coupons for true best back/lay prices with sizes — the fair line used for EV"
            className="text-xs px-3 py-1.5 rounded border border-[#2e2e35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors disabled:opacity-50"
          >
            {scrapingBetfair ? "Scraping Betfair…" : "⇣ Scrape Betfair"}
          </button>
          <button
            onClick={() => runBet365Scan()}
            disabled={scraping}
            title="Scrapes bet365.com.au AFL/NRL coupons (opens a browser window) and merges the prices into the scan"
            className="text-xs px-3 py-1.5 rounded border border-[#2e2e35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors disabled:opacity-50"
          >
            {scraping ? "Scraping bet365…" : "⇣ Scrape bet365"}
          </button>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["ev"] })}
            disabled={isFetching}
            className="text-xs px-3 py-1.5 rounded border border-[#2e2e35] text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors disabled:opacity-50"
          >
            {isFetching ? "Scanning…" : "↻ Rescan"}
          </button>
        </div>
      </div>
      <p className="text-xs text-zinc-600 mb-5">
        Every bookmaker price vs the Betfair fair line (LAY, power-devigged).{" "}
        {all.length > 0 && (
          <span className="text-zinc-500">
            {positiveCount} +EV of {all.length} prices scanned.
          </span>
        )}
        {scrapeMsg && <span className="ml-2 text-zinc-400">{scrapeMsg}</span>}
      </p>

      <div className="flex flex-wrap gap-3 mb-5">
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={sport}
          onChange={(e) => setSport(e.target.value)}
        >
          {SPORTS.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={market}
          onChange={(e) => setMarket(e.target.value)}
        >
          {MARKETS.map((m) => (
            <option key={m.key} value={m.key}>{m.label}</option>
          ))}
        </select>
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={bookmaker}
          onChange={(e) => setBookmaker(e.target.value)}
        >
          <option value="">All Books</option>
          {bookmakers.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={minEV}
          onChange={(e) => setMinEV(Number(e.target.value))}
        >
          {MIN_EV_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          {DAYS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input
          className="flex-1 min-w-40 bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none placeholder-zinc-600"
          placeholder="Search event or team…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-zinc-500 select-none cursor-pointer">
          <input
            type="checkbox"
            checked={pricedOnly}
            onChange={(e) => setPricedOnly(e.target.checked)}
            className="accent-zinc-400"
          />
          Betfair-priced only
        </label>
      </div>

      {isLoading && <div className="text-zinc-500 text-sm">Scanning markets…</div>}
      {isError && (
        <div className="text-red-400 text-sm">Failed to scan — check the backend is running.</div>
      )}
      {!isLoading && !isError && rows.length === 0 && (
        <div className="text-center py-16 text-zinc-600 text-sm">
          No opportunities match the current filters
        </div>
      )}

      {rows.length > 0 && (
        <div className="border border-[#2e2e35] rounded-lg overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-zinc-600 uppercase bg-[#111113]">
                <th className="px-4 py-2.5 text-left">Kickoff</th>
                <th className="px-4 py-2.5 text-left">Event</th>
                <th className="px-4 py-2.5 text-left">Market</th>
                <th className="px-4 py-2.5 text-left">Selection</th>
                <th className="px-4 py-2.5 text-left">Book</th>
                <th className="px-4 py-2.5 text-right">Odds</th>
                <th className="px-4 py-2.5 text-right">Fair</th>
                <th className="px-4 py-2.5 text-right">EV%</th>
                <th className="px-4 py-2.5 text-right">¼ Kelly</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o, i) => (
                <tr
                  key={`${o.event_id}-${o.bookmaker}-${o.market_type}-${o.selection}-${o.line}-${i}`}
                  className="border-t border-[#1e1e22] hover:bg-[#161618]"
                >
                  <td className="px-4 py-2 text-xs text-zinc-500 whitespace-nowrap">
                    {fmtKickoff(o.commence_time)}
                  </td>
                  <td className="px-4 py-2 text-sm text-zinc-300">
                    <div>{o.event_name}</div>
                    <div className="text-xs text-zinc-600">{o.sport_title}</div>
                  </td>
                  <td className="px-4 py-2 text-sm text-zinc-400 whitespace-nowrap">{fmtMarket(o)}</td>
                  <td className="px-4 py-2 text-sm text-zinc-200">{o.selection}</td>
                  <td className="px-4 py-2 text-sm text-zinc-300">{o.bookmaker_title}</td>
                  <td className="px-4 py-2 font-mono text-sm text-zinc-200 text-right">
                    {o.odds.toFixed(2)}
                  </td>
                  <td
                    className="px-4 py-2 font-mono text-sm text-zinc-400 text-right"
                    title={o.reference === "betfair_lay" ? "Betfair LAY, power-devigged" : "No usable Betfair LAY for this market/line"}
                  >
                    {o.fair_odds != null ? o.fair_odds.toFixed(2) : "—"}
                  </td>
                  <td className={`px-4 py-2 font-mono text-sm text-right ${evColor(o.ev_pct)}`}>
                    {fmtPct(o.ev_pct)}
                  </td>
                  <td className="px-4 py-2 font-mono text-sm text-zinc-400 text-right">
                    {o.kelly_pct != null && o.kelly_pct > 0
                      ? `${(o.kelly_pct / 4).toFixed(2)}%`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      className="text-xs text-zinc-400 hover:text-zinc-200 border border-[#2e2e35] hover:border-zinc-500 rounded px-2 py-1 transition-colors"
                      onClick={() => track(o)}
                    >
                      Track
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-3 text-xs text-zinc-700">
        EV is only shown against a usable Betfair LAY (power-devigged, sanity-checked against
        BACK). Rows without one — thin books, or spread/total markets where no lay is available
        at the same line — show "—".
      </p>
    </div>
  );
}
