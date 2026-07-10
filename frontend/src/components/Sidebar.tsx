import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchBets } from "../lib/api";

const NAV = [
  { to: "/", label: "Dashboard", icon: "◈" },
  { to: "/bets/open", label: "Open Bets", icon: "◉", badge: true },
  { to: "/ev", label: "Find EV", icon: "Σ" },
  { to: "/upcoming", label: "Upcoming", icon: "◷" },
  { to: "/bets/add", label: "Add Bet", icon: "+" },
  { to: "/history", label: "History", icon: "▤" },
];

export default function Sidebar() {
  const { data: openBets } = useQuery({
    queryKey: ["bets", { status: "open" }],
    queryFn: () => fetchBets({ status: "open" }),
    refetchInterval: 30_000,
  });

  const openCount = openBets?.length ?? 0;

  return (
    <aside className="w-52 shrink-0 border-r border-[#2e2e35] bg-[#111113] flex flex-col">
      <div className="px-5 py-5 border-b border-[#2e2e35]">
        <span className="font-mono text-sm font-semibold tracking-widest text-zinc-300 uppercase">
          DegenTracker
        </span>
      </div>
      <nav className="flex-1 py-4 flex flex-col gap-0.5 px-2">
        {NAV.map(({ to, label, icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? "bg-[#222226] text-white"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-[#18181b]"
              }`
            }
          >
            <span className="w-4 text-center font-mono text-base">{icon}</span>
            <span className="flex-1">{label}</span>
            {badge && openCount > 0 && (
              <span className="font-mono text-xs bg-zinc-700 text-zinc-200 rounded px-1.5 py-0.5">
                {openCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-[#2e2e35] text-xs text-zinc-600 font-mono">
        v0.1.0
      </div>
    </aside>
  );
}
