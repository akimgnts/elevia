import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AnalyzePage from "./pages/AnalyzePage";
import ProfilePage from "./pages/ProfilePage";
import ProfileUnderstandingPage from "./pages/ProfileUnderstandingPage";
import DashboardPage from "./pages/DashboardPage";
import MatchPage from "./pages/MatchPage";
import OffersPage from "./pages/OffersPage";
import OfferDetailPage from "./pages/OfferDetailPage";
import NotFoundPage from "./pages/NotFoundPage";
import DemoPage from "./pages/DemoPage";
import InboxPage from "./pages/InboxPage";
import AdCoachTestPage from "./pages/AdCoachTestPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import CvDeltaPage from "./pages/CvDeltaPage";
import MarketInsightsPage from "./pages/MarketInsightsPage";
import LoginPage from "./pages/LoginPage";
import MatchingShowcasePage from "./pages/MatchingShowcasePage";
import { useAuth } from "./hooks/useAuth";

function AuthBootstrap() {
  const { sessionChecked, isChecking, restoreSession } = useAuth();

  useEffect(() => {
    if (!sessionChecked && !isChecking) {
      void restoreSession();
    }
  }, [isChecking, restoreSession, sessionChecked]);

  return null;
}

export default function App() {
  return (
    <>
      <AuthBootstrap />
      <Routes>
        <Route path="/" element={<AdCoachTestPage />} />
        <Route path="/landing" element={<AdCoachTestPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/analyse" element={<Navigate to="/analyze" replace />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/ad-coaching" element={<AdCoachTestPage />} />
        <Route path="/adcoach-test" element={<Navigate to="/ad-coaching" replace />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/profile-understanding" element={<ProfileUnderstandingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/cockpit" element={<DashboardPage />} />
        <Route path="/match" element={<MatchPage />} />
        <Route path="/offres" element={<OffersPage />} />
        <Route path="/offers" element={<OffersPage />} />
        <Route path="/explorer" element={<Navigate to="/offers" replace />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/candidatures" element={<ApplicationsPage />} />
        <Route path="/dev/cv-delta" element={<CvDeltaPage />} />
        <Route path="/market-insights" element={<MarketInsightsPage />} />
        <Route path="/market" element={<MarketInsightsPage />} />
        <Route path="/matching-showcase" element={<MatchingShowcasePage />} />
        <Route path="/offers/:offerId" element={<OfferDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
