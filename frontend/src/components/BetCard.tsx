import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ApiBet } from "../lib/api";
import { patchBetResult } from "../lib/api";
import CashoutBadge from "./CashoutBadge";

function marketLabel(bet: ApiBet): string {
  if (bet.market_type === "h2h") return "H2H";
  if (bet.market_type === "totals") {
    return `${bet.side === "over" ? "Over" : "Under"} ${bet.line ?? ""}`;
  }
  if (bet.market_type === "handicap") {
    const side = bet.side === "home" ? "Home" : "Away";
    const line = bet.line != null ? (bet.line > 0 ? `+${bet.line}` : String(bet.line)) : "";
    return `${side} ${line}`;
  }
  return bet.market_type;
}

function countdown(isoTime: string): string {
  const diff = new Date(isoTime).getTime() - Date.now();
  if (diff <= 0) return "Started";
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  if (h > 24) return new Date(isoTime).toLocaleDateString("en-AU", { timeZone: "Australia/Sydney" });
  return `${h}h ${m}m`;
}

export default function BetCard({ bet }: { bet: ApiBet }) {
  const qc = useQueryClient();
  const { mutate: settle, isPending } = useMutation({
    mutationFn: (outcome: "won" | "lost" | "void") => patchBetResult(bet.id, outcome),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bets"] }),
  });

  const isOpen = bet.status === "open";
  const isPastStart = isOpen && new Date(bet.commence_time).getTime() < Date.now();
  const timeLabel = isOpen && !isPastStart ? countdown(bet.commence_time) : null;

  const statusCls =
    bet.status === "won" ? "text-green-400 bg-green-900/30"
    : bet.status === "lost" ? "text-red-400 bg-red-900/30"
    : bet.status === "void" ? "text-zinc-400 bg-zinc-800"
    : "text-amber-400 bg-amber-900/20";
  const statusLabel =
    bet.status === "won" ? "W" : bet.status === "lost" ? "L" : bet.status === "void" ? "V" : "OPEN";

  return (
    <div className="bg-[#111113] border border-[#2e2e35] rounded-lg overflow-hidden">
      <div className="flex items-start justify-between gap-4 px-5 py-4">
        <div className="min-w-0">
          <div className="text-sm text-zinc-400 mb-0.5">{bet.sport_key} · {bet.bookmaker}</div>
          <div className="font-semibold text-white truncate">{bet.event_name}</div>
          <div className="mt-1 font-mono text-sm text-zinc-300">
            {bet.selection} <span className="text-zinc-500 mx-1">·</span> {marketLabel(bet)}
          </div>
        </div>
        <div className="text-right shrink-0">
          <span className={`font-mono text-xs px-1.5 py-0.5 rounded font-semibold ${statusCls}`}>
            {statusLabel}
          </span>
          <div className="font-mono text-xl font-semibold text-white mt-1">{bet.odds_taken.toFixed(2)}</div>
          <div className="font-mono text-sm text-zinc-400">${bet.stake.toFixed(2)}</div>
        </div>
      </div>

      {timeLabel && (
        <div className="px-5 pb-2 text-xs font-mono text-amber-400">⏱ {timeLabel}</div>
      )}

      {isOpen && bet.cashout_signal && (
        <div className="mx-5 mb-4">
          <CashoutBadge signal={bet.cashout_signal} />
        </div>
      )}

      {bet.closing_line && (
        <div className="px-5 pb-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono text-zinc-400">
          {bet.closing_line.betfair_lay_at_bet != null && (
            <><span className="text-zinc-600">Betfair at bet</span><span className="text-zinc-300">{bet.closing_line.betfair_lay_at_bet.toFixed(2)}</span></>
          )}
          {bet.closing_line.betfair_lay_at_close != null && (
            <><span className="text-zinc-600">Betfair close</span><span className="text-zinc-300">{bet.closing_line.betfair_lay_at_close.toFixed(2)}</span></>
          )}
          {bet.closing_line.odds_clv_pct != null && (
            <><span className="text-zinc-600">Odds CLV</span>
            <span className={bet.closing_line.odds_clv_pct >= 0 ? "text-green-400" : "text-red-400"}>
              {bet.closing_line.odds_clv_pct >= 0 ? "+" : ""}{(bet.closing_line.odds_clv_pct * 100).toFixed(2)}%
            </span></>
          )}
          {bet.closing_line.line_clv_pts != null && (
            <><span className="text-zinc-600">Line CLV</span>
            <span className={bet.closing_line.line_clv_pts >= 0 ? "text-green-400" : "text-red-400"}>
              {bet.closing_line.line_clv_pts >= 0 ? "+" : ""}{bet.closing_line.line_clv_pts.toFixed(1)} pts
            </span></>
          )}
          {bet.pnl != null && (
            <><span className="text-zinc-600">P&L</span>
            <span className={bet.pnl >= 0 ? "text-green-400" : "text-red-400"}>
              {bet.pnl >= 0 ? "+" : ""}${bet.pnl.toFixed(2)}
            </span></>
          )}
        </div>
      )}

      {isPastStart && (
        <div className="px-5 pb-4 flex items-center gap-2">
          <span className="text-xs text-zinc-500 mr-2">Pending result:</span>
          <button onClick={() => settle("won")} disabled={isPending}
            className="text-xs font-mono px-3 py-1.5 rounded bg-green-900/30 text-green-400 hover:bg-green-900/50 border border-green-900 transition-colors disabled:opacity-50">
            ✅ Won
          </button>
          <button onClick={() => settle("lost")} disabled={isPending}
            className="text-xs font-mono px-3 py-1.5 rounded bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-900 transition-colors disabled:opacity-50">
            ❌ Lost
          </button>
          <button onClick={() => settle("void")} disabled={isPending}
            className="text-xs font-mono px-3 py-1.5 rounded bg-zinc-800 text-zinc-400 hover:bg-zinc-700 border border-zinc-700 transition-colors disabled:opacity-50">
            ⚪ Void
          </button>
        </div>
      )}
    </div>
  );
}
