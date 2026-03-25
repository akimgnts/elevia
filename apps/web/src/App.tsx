import { Navigate, Route, Routes } from "react-router-dom";
import AnalyzePage from "./pages/AnalyzePage";
import ProfilePage from "./pages/ProfilePage";
import DashboardPage from "./pages/DashboardPage";
import MatchPage from "./pages/MatchPage";
import OffersPage from "./pages/OffersPage";
import ExplorePage from "./pages/ExplorePage";
import LandingPage from "./pages/LandingPage";
import OfferDetailPage from "./pages/OfferDetailPage";
import NotFoundPage from "./pages/NotFoundPage";
import DemoPage from "./pages/DemoPage";
import InboxPage from "./pages/InboxPage";
import AdCoachTestPage from "./pages/AdCoachTestPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import CvDeltaPage from "./pages/CvDeltaPage";
import MarketInsightsPage from "./pages/MarketInsightsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AdCoachTestPage />} />
      <Route path="/landing" element={<LandingPage />} />
      <Route path="/analyze" element={<AnalyzePage />} />
      <Route path="/analyse" element={<Navigate to="/analyze" replace />} />
      <Route path="/demo" element={<DemoPage />} />
      <Route path="/ad-coaching" element={<AdCoachTestPage />} />
      <Route path="/adcoach-test" element={<Navigate to="/ad-coaching" replace />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/match" element={<MatchPage />} />
      <Route path="/offres" element={<OffersPage />} />
      <Route path="/explorer" element={<ExplorePage />} />
      <Route path="/inbox" element={<InboxPage />} />
      <Route path="/applications" element={<ApplicationsPage />} />
      <Route path="/dev/cv-delta" element={<CvDeltaPage />} />
      <Route path="/market-insights" element={<MarketInsightsPage />} />
      <Route path="/offers/:offerId" element={<OfferDetailPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
