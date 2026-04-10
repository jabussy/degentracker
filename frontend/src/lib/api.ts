const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface ApiEvent {
  id: string;
  sport_key: string;
  sport_title: string;
  commence_time: string;
  home_team: string;
  away_team: string;
  status: string;
  home_score: number | null;
  away_score: number | null;
  event_name: string;
}

export function fetchEvents(sport?: string, days = 3): Promise<ApiEvent[]> {
  const q = new URLSearchParams();
  if (sport) q.set("sport", sport);
  q.set("days", String(days));
  return request(`/events?${q}`);
}

export interface OddsLine {
  bookmaker: string;
  market_type: string;
  selection: string;
  odds: number;
  line: number | null;
  snapshot_time: string;
}

export function fetchEventLines(eventId: string) {
  return request<{ event_id: string; event_name: string; lines: OddsLine[]; bookmakers: unknown[] }>(
    `/events/${eventId}/lines`
  );
}

export function fetchEventBetfair(eventId: string) {
  return request<{
    event_id: string;
    runners: { selection_name: string; lay_price: number; size_available: number; snapshot_time: string }[];
  }>(`/events/${eventId}/betfair`);
}

export interface ClosingLine {
  betfair_lay_at_bet: number | null;
  betfair_lay_at_close: number | null;
  odds_clv_pct: number | null;
  beat_closing_odds: boolean | null;
  line_at_open: number | null;
  line_at_close: number | null;
  line_clv_pts: number | null;
  beat_closing_line: boolean | null;
  captured_at: string | null;
  capture_source: string | null;
}

export interface CashoutSignal {
  recommend_cashout: boolean;
  severity: "clear" | "watch" | "cashout";
  original_edge_pct: number;
  current_edge_pct: number;
  current_betfair_lay: number;
}

export interface ApiBet {
  id: number;
  event_id: string;
  sport_key: string;
  event_name: string;
  commence_time: string;
  selection: string;
  market_type: "h2h" | "handicap" | "totals";
  line: number | null;
  side: string;
  odds_taken: number;
  stake: number;
  bookmaker: string;
  status: string;
  settle_source: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  pnl: number | null;
  closing_line: ClosingLine | null;
  cashout_signal?: CashoutSignal | null;
}

export type BetFilters = {
  status?: string;
  sport?: string;
  bookmaker?: string;
  market_type?: string;
};

export function fetchBets(filters?: BetFilters): Promise<ApiBet[]> {
  const q = new URLSearchParams();
  if (filters?.status) q.set("status", filters.status);
  if (filters?.sport) q.set("sport", filters.sport);
  if (filters?.bookmaker) q.set("bookmaker", filters.bookmaker);
  if (filters?.market_type) q.set("market_type", filters.market_type);
  return request(`/bets?${q}`);
}

export function fetchBet(id: number): Promise<ApiBet> {
  return request(`/bets/${id}`);
}

export interface CreateBetPayload {
  event_id: string;
  sport_key: string;
  selection: string;
  market_type: string;
  line?: number | null;
  side: string;
  odds_taken: number;
  stake: number;
  bookmaker: string;
  notes?: string;
}

export function createBet(payload: CreateBetPayload): Promise<ApiBet> {
  return request("/bets", { method: "POST", body: JSON.stringify(payload) });
}

export function patchBetResult(id: number, outcome: "won" | "lost" | "void") {
  return request(`/bets/${id}/result`, {
    method: "PATCH",
    body: JSON.stringify({ outcome }),
  });
}

export function deleteBet(id: number) {
  return request(`/bets/${id}`, { method: "DELETE" });
}

export interface StatsSummary {
  total_staked: number;
  net_pnl: number;
  roi_pct: number;
  settled_count: number;
  open_count: number;
  total_exposure: number;
  odds_clv_win_rate_pct: number | null;
  line_clv_win_rate_pct: number | null;
  avg_odds_clv_pct: number | null;
  avg_line_clv_pts: number | null;
}

export function fetchStatsSummary(): Promise<StatsSummary> {
  return request("/stats/summary");
}

export interface StatsBreakdown {
  group_by: string;
  breakdown: Record<string, StatsSummary>;
}

export function fetchStatsBreakdown(groupBy: "sport" | "bookmaker" | "market_type"): Promise<StatsBreakdown> {
  return request(`/stats/breakdown?group_by=${groupBy}`);
}
