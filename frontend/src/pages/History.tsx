import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchBets, fetchStatsSummary, type ApiBet } from "../lib/api";

const BOOKMAKERS = ["", "tab", "sportsbet", "neds", "pointsbet", "betfair"];
const MARKETS = ["", "h2h", "handicap", "totals"];
const OUTCOMES = ["", "won", "lost", "void"];

function ExpandedRow({ bet }: { bet: ApiBet }) {
  const cl = bet.closing_line;
  if (!cl) return <div className="px-6 py-4 text-zinc-600 text-sm">No closing line data captured</div>;
  return (
    <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-3 gap-4 bg-[#0e0e10]">
      <div><div className="text-xs text-zinc-600 mb-1">Betfair at bet</div><div className="font-mono text-sm text-zinc-300">{cl.betfair_lay_at_bet?.toFixed(2) ?? "—"}</div></div>
      <div><div className="text-xs text-zinc-600 mb-1">Betfair at close</div><div className="font-mono text-sm text-zinc-300">{cl.betfair_lay_at_close?.toFixed(2) ?? "—"}</div></div>
      <div>
        <div className="text-xs text-zinc-600 mb-1">Odds CLV</div>
        {cl.odds_clv_pct != null
          ? <div className={`font-mono text-sm ${cl.odds_clv_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{cl.odds_clv_pct >= 0 ? "+" : ""}{(cl.odds_clv_pct * 100).toFixed(2)}%</div>
          : <div className="font-mono text-sm text-zinc-600">—</div>}
      </div>
      {bet.market_type !== "h2h" && (
        <>
          <div><div className="text-xs text-zinc-600 mb-1">Line at open</div><div className="font-mono text-sm text-zinc-300">{cl.line_at_open ?? "—"}</div></div>
          <div><div className="text-xs text-zinc-600 mb-1">Line at close</div><div className="font-mono text-sm text-zinc-300">{cl.line_at_close ?? "—"}</div></div>
          <div>
            <div className="text-xs text-zinc-600 mb-1">Line CLV</div>
            {cl.line_clv_pts != null
              ? <div className={`font-mono text-sm ${cl.line_clv_pts >= 0 ? "text-green-400" : "text-red-400"}`}>{cl.line_clv_pts >= 0 ? "+" : ""}{cl.line_clv_pts.toFixed(1)} pts</div>
              : <div className="font-mono text-sm text-zinc-600">—</div>}
          </div>
        </>
      )}
      <div className="col-span-2 md:col-span-3 text-xs text-zinc-600">
        {cl.capture_source && <>Captured via {cl.capture_source} · </>}
        {cl.captured_at && new Date(cl.captured_at).toLocaleString("en-AU", { timeZone: "Australia/Sydney" })}
      </div>
    </div>
  );
}

function BetRow({ bet }: { bet: ApiBet }) {
  const [open, setOpen] = useState(false);
  const cl = bet.closing_line;
  return (
    <>
      <tr onClick={() => setOpen(!open)} className="border-b border-[#1e1e22] hover:bg-[#161618] cursor-pointer">
        <td className="px-4 py-3 text-xs text-zinc-500 font-mono">{new Date(bet.updated_at).toLocaleDateString("en-AU", { timeZone: "Australia/Sydney" })}</td>
        <td className="px-4 py-3"><div className="text-sm text-zinc-300 truncate max-w-48">{bet.event_name}</div><div className="text-xs text-zinc-500">{bet.selection}</div></td>
        <td className="px-4 py-3 text-xs text-zinc-500">{bet.market_type}</td>
        <td className="px-4 py-3 font-mono text-xs text-zinc-400">{bet.line != null ? String(bet.line) : "—"}</td>
        <td className="px-4 py-3 font-mono text-sm text-zinc-200">{bet.odds_taken.toFixed(2)}</td>
        <td className="px-4 py-3 font-mono text-xs text-zinc-300">${bet.stake}</td>
        <td className="px-4 py-3">
          <span className={`font-mono text-xs px-1.5 py-0.5 rounded font-semibold ${bet.status === "won" ? "text-green-400 bg-green-900/30" : bet.status === "lost" ? "text-red-400 bg-red-900/30" : "text-zinc-400 bg-zinc-800"}`}>
            {bet.status === "won" ? "W" : bet.status === "lost" ? "L" : "V"}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-sm">
          {bet.pnl != null ? <span className={bet.pnl >= 0 ? "text-green-400" : "text-red-400"}>{bet.pnl >= 0 ? "+" : ""}${bet.pnl.toFixed(2)}</span> : <span className="text-zinc-600">—</span>}
        </td>
        <td className="px-4 py-3 font-mono text-xs">
          {cl?.odds_clv_pct != null ? <span className={cl.odds_clv_pct >= 0 ? "text-green-400" : "text-red-400"}>{cl.odds_clv_pct >= 0 ? "+" : ""}{(cl.odds_clv_pct * 100).toFixed(2)}%</span> : <span className="text-zinc-600">—</span>}
        </td>
        <td className="px-4 py-3 font-mono text-xs">
          {cl?.line_clv_pts != null ? <span className={cl.line_clv_pts >= 0 ? "text-green-400" : "text-red-400"}>{cl.line_clv_pts >= 0 ? "+" : ""}{cl.line_clv_pts.toFixed(1)} pts</span> : <span className="text-zinc-600">—</span>}
        </td>
      </tr>
      {open && <tr className="border-b border-[#1e1e22]"><td colSpan={10} className="p-0"><ExpandedRow bet={bet} /></td></tr>}
    </>
  );
}

export default function History() {
  const [sport, setSport] = useState("");
  const [bookmaker, setBookmaker] = useState("");
  const [market, setMarket] = useState("");
  const [outcome, setOutcome] = useState("");

  const { data: bets = [], isLoading } = useQuery({
    queryKey: ["bets", { sport, bookmaker, market_type: market }],
    queryFn: () => fetchBets({ sport: sport || undefined, bookmaker: bookmaker || undefined, market_type: market || undefined }),
    staleTime: 30_000,
  });

  const { data: summary } = useQuery({ queryKey: ["stats", "summary"], queryFn: fetchStatsSummary, staleTime: 60_000 });

  const settled = bets
    .filter((b) => ["won", "lost", "void"].includes(b.status))
    .filter((b) => !outcome || b.status === outcome)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

  const sel = "bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none";

  return (
    <div className="p-6 max-w-7xl">
      <h1 className="text-lg font-semibold text-zinc-200 mb-6">History & CLV</h1>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 bg-[#111113] border border-[#2e2e35] rounded-lg p-5">
          <div><div className="text-xs text-zinc-600 mb-1">Odds CLV win rate</div><div className={`font-mono text-lg font-semibold ${(summary.odds_clv_win_rate_pct ?? 0) >= 50 ? "text-green-400" : "text-red-400"}`}>{summary.odds_clv_win_rate_pct != null ? `${summary.odds_clv_win_rate_pct.toFixed(1)}%` : "—"}</div></div>
          <div><div className="text-xs text-zinc-600 mb-1">Line CLV win rate</div><div className={`font-mono text-lg font-semibold ${(summary.line_clv_win_rate_pct ?? 0) >= 50 ? "text-green-400" : "text-red-400"}`}>{summary.line_clv_win_rate_pct != null ? `${summary.line_clv_win_rate_pct.toFixed(1)}%` : "—"}</div></div>
          <div><div className="text-xs text-zinc-600 mb-1">Avg odds CLV</div><div className={`font-mono text-lg font-semibold ${(summary.avg_odds_clv_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>{summary.avg_odds_clv_pct != null ? `${summary.avg_odds_clv_pct >= 0 ? "+" : ""}${summary.avg_odds_clv_pct.toFixed(2)}%` : "—"}</div></div>
          <div><div className="text-xs text-zinc-600 mb-1">Avg line CLV</div><div className={`font-mono text-lg font-semibold ${(summary.avg_line_clv_pts ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>{summary.avg_line_clv_pts != null ? `${summary.avg_line_clv_pts >= 0 ? "+" : ""}${summary.avg_line_clv_pts.toFixed(2)} pts` : "—"}</div></div>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-5">
        <select className={sel} value={sport} onChange={(e) => setSport(e.target.value)}><option value="">All Sports</option>{[["aussierules_afl","AFL"],["rugbyleague_nrl","NRL"],["basketball_nba","NBA"],["americanfootball_nfl","NFL"]].map(([k,l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select className={sel} value={bookmaker} onChange={(e) => setBookmaker(e.target.value)}><option value="">All Bookmakers</option>{["tab","sportsbet","neds","pointsbet","bet365","betfair"].map((b) => <option key={b} value={b}>{b}</option>)}</select>
        <select className={sel} value={market} onChange={(e) => setMarket(e.target.value)}><option value="">All Markets</option>{MARKETS.filter(Boolean).map((m) => <option key={m} value={m}>{m}</option>)}</select>
        <select className={sel} value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="">All Outcomes</option>{OUTCOMES.filter(Boolean).map((o) => <option key={o} value={o}>{o}</option>)}</select>
      </div>

      {isLoading && <div className="text-zinc-500 text-sm">Loading…</div>}

      <div className="bg-[#111113] border border-[#2e2e35] rounded-lg overflow-hidden overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#2e2e35]">
              {["Date","Event","Market","Line","Odds","Stake","Result","P&L","Odds CLV%","Line CLV pts"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs text-zinc-600 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {settled.length === 0
              ? <tr><td colSpan={10} className="px-4 py-12 text-center text-zinc-600 text-sm">No settled bets</td></tr>
              : settled.map((b) => <BetRow key={b.id} bet={b} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
