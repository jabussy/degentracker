import { useQuery } from "@tanstack/react-query";
import { fetchBets } from "../lib/api";
import BetCard from "../components/BetCard";

export default function OpenBets() {
  const { data: bets = [], isLoading, error } = useQuery({
    queryKey: ["bets", { status: "open" }],
    queryFn: () => fetchBets({ status: "open" }),
    refetchInterval: 30_000,
  });

  const totalExposure = bets.reduce((sum, b) => sum + b.stake, 0);

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold text-zinc-200">Open Bets</h1>
        <div className="font-mono text-sm text-zinc-400">
          {bets.length} open · <span className="text-zinc-300">${totalExposure.toFixed(2)}</span> exposure
        </div>
      </div>
      {isLoading && <div className="text-zinc-500 text-sm">Loading…</div>}
      {error && <div className="text-red-400 text-sm">Error loading bets</div>}
      {!isLoading && bets.length === 0 && (
        <div className="text-center py-16 text-zinc-600">
          <div className="text-2xl mb-2">◉</div>
          <div className="text-sm">No open bets</div>
        </div>
      )}
      <div className="flex flex-col gap-4">
        {bets.map((bet) => <BetCard key={bet.id} bet={bet} />)}
      </div>
    </div>
  );
}
