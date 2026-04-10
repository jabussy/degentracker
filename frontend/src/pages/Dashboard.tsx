import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { useState } from "react";
import { fetchStatsSummary, fetchBets, type ApiBet } from "../lib/api";
import StatCard from "../components/StatCard";

type Window = "30bets" | "90days" | "all";

function pnlSeries(bets: ApiBet[]) {
  const settled = bets
    .filter((b) => b.status !== "open" && b.status !== "deleted" && b.pnl != null)
    .sort((a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
  let cumulative = 0;
  return settled.map((b) => {
    cumulative += b.pnl!;
    return {
      label: new Date(b.updated_at).toLocaleDateString("en-AU", { timeZone: "Australia/Sydney" }),
      pnl: Math.round(cumulative * 100) / 100,
      event: b.event_name,
    };
  });
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { label: string; pnl: number; event: string } }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#18181b] border border-[#2e2e35] rounded px-3 py-2 text-xs font-mono">
      <div className="text-zinc-400">{d.label}</div>
      <div className={d.pnl >= 0 ? "text-green-400" : "text-red-400"}>
        {d.pnl >= 0 ? "+" : ""}${d.pnl.toFixed(2)}
      </div>
      <div className="text-zinc-500 truncate max-w-40">{d.event}</div>
    </div>
  );
}

export default function Dashboard() {
  const [window_, setWindow] = useState<Window>("30bets");

  const {
    data: summary,
    isLoading: sumLoading,
    isError: sumError,
  } = useQuery({
    queryKey: ["stats", "summary"],
    queryFn: fetchStatsSummary,
    refetchInterval: 60_000,
  });

  const { data: allBets = [] } = useQuery({
    queryKey: ["bets"],
    queryFn: () => fetchBets(),
    refetchInterval: 30_000,
  });

  const series = pnlSeries(allBets);
  const displaySeries =
    window_ === "30bets"
      ? series.slice(-30)
      : window_ === "90days"
      ? series.filter((_, i, arr) => i >= arr.length - 90)
      : series;

  const recentSettled = allBets
    .filter((b) => ["won", "lost", "void"].includes(b.status))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  const netPnl = summary?.net_pnl ?? 0;
  const pnlColor = netPnl >= 0 ? ("green" as const) : ("red" as const);
  const noBets = !sumLoading && !sumError && summary && summary.settled_count === 0 && summary.open_count === 0;

  function fmtMoney(val: number | undefined): string {
    return `$${(val ?? 0).toFixed(2)}`;
  }

  function fmtPct(val: number | undefined): string {
    const v = val ?? 0;
    return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  }

  return (
    <div className="p-6 max-w-6xl">
      <h1 className="text-lg font-semibold text-zinc-200 mb-6">Dashboard</h1>

      {sumError && (
        <div className="mb-4 px-4 py-3 bg-red-900/20 border border-red-900 rounded text-red-400 text-sm">
          Failed to load stats — check the backend is running.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Staked"
          value={sumLoading ? "…" : fmtMoney(summary?.total_staked)}
        />
        <StatCard
          label="Net P&L"
          value={sumLoading ? "…" : `${netPnl >= 0 ? "+" : ""}${fmtMoney(Math.abs(netPnl))}`}
          color={pnlColor}
        />
        <StatCard
          label="ROI"
          value={sumLoading ? "…" : fmtPct(summary?.roi_pct)}
          color={pnlColor}
        />
        <StatCard
          label="CLV Win Rate"
          value={
            sumLoading
              ? "…"
              : summary?.odds_clv_win_rate_pct != null
              ? `${summary.odds_clv_win_rate_pct.toFixed(1)}%`
              : "—"
          }
          sub="odds CLV"
          color={(summary?.odds_clv_win_rate_pct ?? 0) >= 50 ? "green" : "red"}
        />
      </div>

      <div className="mb-6 flex gap-6 text-sm font-mono text-zinc-400">
        <span>
          <span className="text-zinc-600">Open:</span>{" "}
          <span className="text-zinc-200">{summary?.open_count ?? "—"}</span>
        </span>
        <span>
          <span className="text-zinc-600">Exposure:</span>{" "}
          <span className="text-zinc-200">{fmtMoney(summary?.total_exposure)}</span>
        </span>
        <span>
          <span className="text-zinc-600">Settled:</span>{" "}
          <span className="text-zinc-200">{summary?.settled_count ?? "—"}</span>
        </span>
      </div>

      {noBets && (
        <div className="mb-6 px-5 py-4 bg-[#111113] border border-[#2e2e35] rounded-lg text-center text-zinc-500 text-sm">
          No bets tracked yet — add your first bet to get started.
        </div>
      )}

      <div className="bg-[#111113] border border-[#2e2e35] rounded-lg p-5 mb-8">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-zinc-400">Running P&L</span>
          <div className="flex gap-1">
            {(["30bets", "90days", "all"] as Window[]).map((w) => (
              <button
                key={w}
                onClick={() => setWindow(w)}
                className={`text-xs font-mono px-2.5 py-1 rounded transition-colors ${
                  window_ === w
                    ? "bg-zinc-700 text-zinc-200"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {w === "30bets" ? "30 bets" : w === "90days" ? "90d" : "All"}
              </button>
            ))}
          </div>
        </div>
        {displaySeries.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-zinc-600 text-sm">
            No settled bets yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={displaySeries}>
              <XAxis dataKey="label" hide />
              <YAxis
                tickFormatter={(v) => `$${v}`}
                tick={{ fill: "#71717a", fontSize: 11, fontFamily: "monospace" }}
                width={60}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: "#22c55e" }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-[#111113] border border-[#2e2e35] rounded-lg">
        <div className="px-5 py-4 border-b border-[#2e2e35] text-sm text-zinc-400">Recent Settled</div>
        {recentSettled.length === 0 ? (
          <div className="px-5 py-8 text-center text-zinc-600 text-sm">No settled bets</div>
        ) : (
          <div className="divide-y divide-[#1e1e22]">
            {recentSettled.map((b) => (
              <div key={b.id} className="flex items-center gap-4 px-5 py-3">
                <span
                  className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded ${
                    b.status === "won"
                      ? "text-green-400 bg-green-900/30"
                      : b.status === "lost"
                      ? "text-red-400 bg-red-900/30"
                      : "text-zinc-400 bg-zinc-800"
                  }`}
                >
                  {b.status === "won" ? "W" : b.status === "lost" ? "L" : "V"}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-zinc-300 truncate">{b.event_name}</div>
                  <div className="text-xs text-zinc-500 font-mono">
                    {b.selection} · {b.odds_taken.toFixed(2)} · ${b.stake}
                  </div>
                </div>
                <div
                  className={`font-mono text-sm font-semibold ${
                    (b.pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {(b.pnl ?? 0) >= 0 ? "+" : ""}${(b.pnl ?? 0).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
