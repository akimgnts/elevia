import { Navigate, Route, Routes } from "react-router-dom";
import AnalyzePage from "./pages/AnalyzePage";
import ProfilePage from "./pages/ProfilePage";
import DashboardPage from "./pages/DashboardPage";
import MatchPage from "./pages/MatchPage";
import OffersPage from "./pages/OffersPage";
import LandingPage from "./pages/LandingPage";
import OfferDetailPage from "./pages/OfferDetailPage";
import NotFoundPage from "./pages/NotFoundPage";
import DemoPage from "./pages/DemoPage";
import InboxPage from "./pages/InboxPage";
import AdCoachTestPage from "./pages/AdCoachTestPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import DevCvDeltaPage from "./pages/DevCvDeltaPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/analyze" element={<AnalyzePage />} />
      <Route path="/analyse" element={<Navigate to="/analyze" replace />} />
      <Route path="/demo" element={<DemoPage />} />
      <Route path="/adcoach-test" element={<AdCoachTestPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/match" element={<MatchPage />} />
      <Route path="/offres" element={<OffersPage />} />
      <Route path="/inbox" element={<InboxPage />} />
      <Route path="/applications" element={<ApplicationsPage />} />
      <Route path="/dev/cv-delta" element={<DevCvDeltaPage />} />
      <Route path="/offers/:offerId" element={<OfferDetailPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
