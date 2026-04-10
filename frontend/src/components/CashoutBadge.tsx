import type { CashoutSignal } from "../lib/api";

interface Props {
  signal: CashoutSignal;
}

const CONFIG = {
  clear: {
    label: "Holding Value",
    border: "border-l-green-500",
    bg: "bg-[#0d1f14]",
    text: "text-green-400",
    dot: "bg-green-500",
    pulse: "",
  },
  watch: {
    label: "Watch",
    border: "border-l-amber-500",
    bg: "bg-[#1f1900]",
    text: "text-amber-400",
    dot: "bg-amber-500",
    pulse: "",
  },
  cashout: {
    label: "Consider Cashout",
    border: "border-l-red-500",
    bg: "bg-[#1f0d0d]",
    text: "text-red-400",
    dot: "bg-red-500",
    pulse: "pulse-red",
  },
  unavailable: {
    label: "Betfair data unavailable",
    border: "border-l-zinc-600",
    bg: "bg-[#111113]",
    text: "text-zinc-500",
    dot: "bg-zinc-600",
    pulse: "",
  },
};

export default function CashoutBadge({ signal }: Props) {
  const cfg = CONFIG[signal.severity] ?? CONFIG.unavailable;

  if (signal.severity === "unavailable") {
    return (
      <div className={`border-l-4 ${cfg.border} ${cfg.bg} rounded-r px-4 py-3`}>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
          <span className={`text-sm ${cfg.text}`}>{cfg.label}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`border-l-4 ${cfg.border} ${cfg.bg} ${cfg.pulse} rounded-r px-4 py-3`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
        <span className={`text-sm font-semibold ${cfg.text}`}>{cfg.label}</span>
      </div>
      <div className="font-mono text-xs text-zinc-400 flex gap-4">
        <span>
          Original:{" "}
          <span className={(signal.original_edge_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}>
            {(signal.original_edge_pct ?? 0) >= 0 ? "+" : ""}
            {(signal.original_edge_pct ?? 0).toFixed(2)}%
          </span>
        </span>
        <span>
          Current:{" "}
          <span className={(signal.current_edge_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400"}>
            {(signal.current_edge_pct ?? 0) >= 0 ? "+" : ""}
            {(signal.current_edge_pct ?? 0).toFixed(2)}%
          </span>
        </span>
        <span className="text-zinc-500">
          LAY:{" "}
          <span className="text-zinc-300">
            {signal.current_betfair_lay?.toFixed(2) ?? "—"}
          </span>
        </span>
      </div>
    </div>
  );
}
