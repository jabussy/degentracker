interface StatCardProps {
  label: string;
  value: string | number | null;
  sub?: string;
  color?: "default" | "green" | "red" | "amber";
}

export default function StatCard({ label, value, sub, color = "default" }: StatCardProps) {
  const valueColor =
    color === "green" ? "text-green-400"
    : color === "red" ? "text-red-400"
    : color === "amber" ? "text-amber-400"
    : "text-white";

  return (
    <div className="bg-[#111113] border border-[#2e2e35] rounded-lg px-5 py-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">{label}</div>
      <div className={`font-mono text-2xl font-semibold ${valueColor}`}>{value ?? "—"}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1 font-mono">{sub}</div>}
    </div>
  );
}
