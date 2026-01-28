import { Suspense, lazy } from "react";
import { Navbar } from "../components/layout/Navbar";
import { HeroSection } from "../components/landing/HeroSection";
import { HowItWorks } from "../components/landing/HowItWorks";
import { CTAUploadBlock } from "../components/landing/CTAUploadBlock";
import { WhyElevia } from "../components/landing/WhyElevia";
import { HeroVisualLayer } from "../components/landing/HeroVisualLayer";
import { LandingFooter } from "../components/landing/LandingFooter";
import { layout, typography } from "../styles/uiTokens";

const Testimonials = lazy(() => import("../components/landing/Testimonials").then((m) => ({ default: m.Testimonials })));
const PricingSection = lazy(() => import("../components/landing/PricingSection").then((m) => ({ default: m.PricingSection })));

function SectionFallback() {
  return (
    <div className={`${layout.section} text-center`}>
      <p className={typography.caption}>Chargement…</p>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="relative min-h-screen bg-gradient-to-b from-surface-muted to-white text-slate-900">
      <HeroVisualLayer />
      <Navbar />
      <main>
        <HeroSection />
        <HowItWorks />
        <CTAUploadBlock />
        <WhyElevia />
        <Suspense fallback={<SectionFallback />}>
          <Testimonials />
        </Suspense>
        <Suspense fallback={<SectionFallback />}>
          <PricingSection />
        </Suspense>
      </main>
      <LandingFooter />
    </div>
  );
}
