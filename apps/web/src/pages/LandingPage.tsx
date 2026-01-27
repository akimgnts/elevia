import { Suspense, lazy } from "react";
import { Navbar } from "../components/layout/Navbar";
import { HeroSection } from "../components/landing/HeroSection";
import { HowItWorks } from "../components/landing/HowItWorks";
import { CTAUploadBlock } from "../components/landing/CTAUploadBlock";
import { WhyElevia } from "../components/landing/WhyElevia";
import { HeroVisualLayer } from "../components/landing/HeroVisualLayer";
import { LandingFooter } from "../components/landing/LandingFooter";

const Testimonials = lazy(() => import("../components/landing/Testimonials").then((m) => ({ default: m.Testimonials })));
const PricingSection = lazy(() => import("../components/landing/PricingSection").then((m) => ({ default: m.PricingSection })));

export default function LandingPage() {
  return (
    <div className="relative bg-white text-slate-900">
      <HeroVisualLayer />
      <Navbar />
      <main>
        <HeroSection />
        <HowItWorks />
        <CTAUploadBlock />
        <WhyElevia />
        <Suspense fallback={<div className="py-10 text-center text-sm text-slate-500">Chargement…</div>}>
          <Testimonials />
        </Suspense>
        <Suspense fallback={<div className="py-10 text-center text-sm text-slate-500">Chargement…</div>}>
          <PricingSection />
        </Suspense>
      </main>
      <LandingFooter />
    </div>
  );
}
