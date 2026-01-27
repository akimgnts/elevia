import { Footer } from "../components/layout/Footer";
import { Navbar } from "../components/layout/Navbar";
import { FinalCTASection } from "../components/sections/FinalCTASection";
import { HeroSection } from "../components/sections/HeroSection";
import { HowItWorksSection } from "../components/sections/HowItWorksSection";
import { LiveDemoSection } from "../components/sections/LiveDemoSection";
import { RecommendedOffersSection } from "../components/sections/RecommendedOffersSection";
import { TestimonialsSection } from "../components/sections/TestimonialsSection";
import { WhyEleviaWorksSection } from "../components/sections/WhyEleviaWorksSection";

export default function HomePage() {
  return (
    <div className="relative">
      <Navbar />
      <main className="bg-gradient-to-b from-white via-slate-50 to-white">
        <HeroSection />
        <HowItWorksSection />
        <WhyEleviaWorksSection />
        <RecommendedOffersSection />
        <TestimonialsSection />
        <LiveDemoSection />
        <FinalCTASection />
      </main>
      <Footer />
    </div>
  );
}
