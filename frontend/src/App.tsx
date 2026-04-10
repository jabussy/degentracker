import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import OpenBets from "./pages/OpenBets";
import AddBet from "./pages/AddBet";
import Upcoming from "./pages/Upcoming";
import History from "./pages/History";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-[#0a0a0b] text-zinc-100">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/bets/open" element={<OpenBets />} />
            <Route path="/bets/add" element={<AddBet />} />
            <Route path="/upcoming" element={<Upcoming />} />
            <Route path="/history" element={<History />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
