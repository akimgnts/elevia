import { Navigate, Route, Routes } from "react-router-dom";
import MatchPage from "./pages/MatchPage";
import OffersPage from "./pages/OffersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/match" replace />} />
      <Route path="/match" element={<MatchPage />} />
      <Route path="/offres" element={<OffersPage />} />
      <Route path="*" element={<div style={{ padding: 24 }}>404</div>} />
    </Routes>
  );
}
