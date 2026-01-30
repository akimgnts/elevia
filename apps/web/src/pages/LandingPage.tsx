import { Suspense, lazy } from "react";
import { Navbar } from "../components/layout/Navbar";
import { HeroSection } from "../components/landing/HeroSection";
import { HowItWorks } from "../components/landing/HowItWorks";
import { CTAUploadBlock } from "../components/landing/CTAUploadBlock";
import { WhyElevia } from "../components/landing/WhyElevia";
import { HeroVisualLayer } from "../components/landing/HeroVisualLayer";
import { LandingFooter } from "../components/landing/LandingFooter";
import { layout } from "../styles/uiTokens";

// Lazy loading pour la performance
const Testimonials = lazy(() => import("../components/landing/Testimonials").then((m) => ({ default: m.Testimonials })));
const PricingSection = lazy(() => import("../components/landing/PricingSection").then((m) => ({ default: m.PricingSection })));

function SectionFallback() {
  return (
    <div className={`${layout.section} flex items-center justify-center`}>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-cyan border-t-transparent" />
    </div>
  );
}

export default function LandingPage() {
  return (
    /* 1. Ajout de antialiased et d'une sélection personnalisée pour le style */
    <div className="relative min-h-screen bg-[#fafafa] text-slate-900 antialiased selection:bg-brand-cyan selection:text-white">
      
      {/* 2. LE GRAIN : La texture qui change tout (à mettre dans ton CSS global idéalement) */}
      <div className="pointer-events-none fixed inset-0 z-50 opacity-[0.03] mix-blend-overlay" 
           style={{ backgroundImage: `url('https://grainy-gradients.vercel.app/noise.svg')` }}></div>

      {/* 3. LES BLOBS : Animation organique en fond */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] h-[600px] w-[600px] animate-pulse rounded-full bg-brand-cyan/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[5%] h-[500px] w-[500px] animate-bounce rounded-full bg-brand-lime/10 blur-[100px] duration-[10s]" />
      </div>

      <Navbar />

      <main className="relative">
        {/* On enveloppe le Hero dans un layer visuel plus profond */}
        <section className="relative overflow-hidden">
          <HeroVisualLayer />
          <HeroSection />
        </section>

        {/* 4. TRANSITION DOUCE : On évite les séparations nettes */}
        <div className="relative z-10 space-y-24 pb-24 md:space-y-32">
          
          <section className="px-4">
             <HowItWorks />
          </section>

          {/* On rend le CTA flottant/détaché pour casser le rythme */}
          <section className="mx-auto max-w-7xl px-4 drop-shadow-[0_20px_50px_rgba(0,0,0,0.05)]">
            <CTAUploadBlock />
          </section>

          <section className="px-4">
            <WhyElevia />
          </section>

          <Suspense fallback={<SectionFallback />}>
            <div className="bg-slate-950 py-24 text-white skew-y-[-1deg] overflow-hidden">
              <div className="skew-y-[1deg]"> {/* On redresse le contenu */}
                <Testimonials />
              </div>
            </div>
          </Suspense>

          <Suspense fallback={<SectionFallback />}>
            <section className="px-4">
              <PricingSection />
            </section>
          </Suspense>
        </div>
      </main>

      <LandingFooter />
    </div>
  );
}
