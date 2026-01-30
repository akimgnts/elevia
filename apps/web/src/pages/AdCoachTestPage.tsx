import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Check,
  ChevronRight,
  Compass,
  FileText,
  Inbox,
  Menu,
  MessageSquare,
  Moon,
  Send,
  Sparkles,
  Sun,
  Target,
} from "lucide-react";

declare global {
  interface Window {
    THREE?: any;
  }
}

const BODY_CLASS =
  "antialiased text-neutral-900 bg-white dark:bg-black dark:text-white transition-colors duration-500 flex flex-col relative overflow-x-hidden selection:bg-emerald-500/30";

export default function AdCoachTestPage() {
  const [activeView, setActiveView] = useState("home");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const threeRef = useRef<{
    renderer?: any;
    scene?: any;
    camera?: any;
    uniforms?: any;
    systemsGroup?: any;
    resizeHandler?: () => void;
    animationId?: number;
    mouseHandler?: (e: MouseEvent) => void;
  }>({});

  const initScrollAnimations = () => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );

    observerRef.current = observer;

    document.querySelectorAll(".reveal-on-scroll").forEach((el) => {
      el.classList.remove("is-visible");
      observer.observe(el);
    });
  };

  const route = (viewId: string) => {
    setActiveView(viewId);
    setMobileOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => initScrollAnimations(), 50);
  };

  const toggleTheme = () => {
    const html = document.documentElement;
    const next = !isDark;
    setIsDark(next);
    if (next) {
      html.classList.add("dark");
      localStorage.setItem("elevia_theme", "dark");
    } else {
      html.classList.remove("dark");
      localStorage.setItem("elevia_theme", "light");
    }
    if (threeRef.current.uniforms) {
      if (next) {
        threeRef.current.uniforms.uColor.value.set("#10b981");
        threeRef.current.uniforms.uOpacity.value = 0.6;
      } else {
        threeRef.current.uniforms.uColor.value.set("#047857");
        threeRef.current.uniforms.uOpacity.value = 0.8;
      }
    }
  };

  useEffect(() => {
    const prevHtmlClass = document.documentElement.className;
    const prevBodyClass = document.body.className;

    document.body.className = BODY_CLASS;

    const saved = localStorage.getItem("elevia_theme");
    const initialDark = saved ? saved === "dark" : true;
    setIsDark(initialDark);
    if (initialDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }

    const onScroll = () => setShowScrollTop(window.scrollY > 400);
    window.addEventListener("scroll", onScroll);

    initScrollAnimations();

    return () => {
      window.removeEventListener("scroll", onScroll);
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      document.documentElement.className = prevHtmlClass;
      document.body.className = prevBodyClass;
    };
  }, []);

  useEffect(() => {
    initScrollAnimations();
  }, [activeView]);

  useEffect(() => {
    let script: HTMLScriptElement | null = null;
    let isCancelled = false;

    const initThree = () => {
      if (isCancelled) return;
      if (!window.THREE || !containerRef.current) return;

      const THREE = window.THREE;
      const container = containerRef.current;
      const scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x000000, 0.02);

      const camera = new THREE.PerspectiveCamera(
        50,
        window.innerWidth / window.innerHeight,
        0.1,
        100
      );
      camera.position.set(0, 0, 18);

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      container.appendChild(renderer.domElement);

      const systemsGroup = new THREE.Group();
      systemsGroup.position.x = 4.5;
      scene.add(systemsGroup);

      const geometry = new THREE.IcosahedronGeometry(4.5, 30);
      const darkModeActive = document.documentElement.classList.contains("dark");
      const uniforms = {
        uTime: { value: 0 },
        uDistortion: { value: 0.6 },
        uSize: { value: 2.5 },
        uColor: { value: new THREE.Color(darkModeActive ? "#10b981" : "#047857") },
        uOpacity: { value: darkModeActive ? 0.6 : 0.8 },
        uMouse: { value: new THREE.Vector2(0, 0) },
      };

      const vertexShader = document.getElementById("vertexShader")?.textContent || "";
      const fragmentShader = document.getElementById("fragmentShader")?.textContent || "";

      const material = new THREE.ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms,
        transparent: true,
        depthWrite: false,
        blending: THREE.NormalBlending,
      });

      const particles = new THREE.Points(geometry, material);
      systemsGroup.add(particles);

      let time = 0;
      let mouseX = 0;
      let mouseY = 0;

      const onMouseMove = (e: MouseEvent) => {
        mouseX = (e.clientX / window.innerWidth) * 2 - 1;
        mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
        uniforms.uMouse.value.x += (mouseX - uniforms.uMouse.value.x) * 0.05;
        uniforms.uMouse.value.y += (mouseY - uniforms.uMouse.value.y) * 0.05;
      };

      document.addEventListener("mousemove", onMouseMove);

      const onResize = () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
        if (window.innerWidth < 768) {
          systemsGroup.position.set(0, 2, -5);
          systemsGroup.scale.set(0.8, 0.8, 0.8);
        } else {
          systemsGroup.position.set(4.5, 0, 0);
          systemsGroup.scale.set(1, 1, 1);
        }
      };

      window.addEventListener("resize", onResize);
      onResize();

      const animate = () => {
        time += 0.01;
        systemsGroup.rotation.y = time * 0.05;
        systemsGroup.rotation.z = time * 0.02;
        uniforms.uTime.value = time;
        renderer.render(scene, camera);
        threeRef.current.animationId = requestAnimationFrame(animate);
      };

      animate();

      threeRef.current = {
        renderer,
        scene,
        camera,
        uniforms,
        systemsGroup,
        resizeHandler: onResize,
        animationId: threeRef.current.animationId,
        mouseHandler: onMouseMove,
      };

      return () => {
        document.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("resize", onResize);
      };
    };

    if (!window.THREE) {
      script = document.createElement("script");
      script.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      script.async = true;
      script.onload = () => initThree();
      document.body.appendChild(script);
    } else {
      initThree();
    }

    return () => {
      isCancelled = true;
      if (threeRef.current.animationId) {
        cancelAnimationFrame(threeRef.current.animationId);
      }
      if (threeRef.current.mouseHandler) {
        document.removeEventListener("mousemove", threeRef.current.mouseHandler);
      }
      if (threeRef.current.resizeHandler) {
        window.removeEventListener("resize", threeRef.current.resizeHandler);
      }
      if (threeRef.current.renderer && containerRef.current) {
        containerRef.current.innerHTML = "";
      }
      if (script) {
        script.remove();
      }
    };
  }, []);

  useEffect(() => {
    if (threeRef.current.uniforms) {
      if (isDark) {
        threeRef.current.uniforms.uColor.value.set("#10b981");
        threeRef.current.uniforms.uOpacity.value = 0.6;
      } else {
        threeRef.current.uniforms.uColor.value.set("#047857");
        threeRef.current.uniforms.uOpacity.value = 0.8;
      }
    }
  }, [isDark]);

  useEffect(() => {
    const section = document.getElementById("decision-lifecycle");
    const header = document.getElementById("lifecycle-header");
    const line = document.getElementById("lifecycle-line");
    const steps = section?.querySelectorAll<HTMLElement>(".lifecycle-step") ?? [];

    if (!section || !header || !line) return;

    const handleScroll = () => {
      const rect = section.getBoundingClientRect();
      const viewH = window.innerHeight;
      const travelDistance = rect.height - viewH;
      const scrolled = -rect.top;
      let progress = travelDistance > 0 ? scrolled / travelDistance : 0;
      progress = Math.max(0, Math.min(1, progress));

      header.style.opacity = progress > 0.02 ? "1" : "0";
      line.style.height = `${progress * 100}%`;

      steps.forEach((step) => {
        const thresholdAttr = step.dataset.threshold;
        const threshold = thresholdAttr ? Number.parseFloat(thresholdAttr) : 0;
        if (Number.isNaN(threshold)) return;
        if (progress >= threshold) {
          if (progress < threshold + 0.15) {
            step.classList.add("active");
            step.classList.remove("opacity-30");
            step.classList.add("opacity-100");
            step.style.transform = "scale(1.05)";
          } else {
            step.classList.add("active");
            step.classList.remove("opacity-30");
            step.classList.add("opacity-50");
            step.style.transform = "scale(1)";
          }
        } else {
          step.classList.remove("active");
          step.classList.remove("opacity-100");
          step.classList.remove("opacity-50");
          step.classList.add("opacity-30");
          step.style.transform = "scale(1)";
        }
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="min-h-screen">
      <style>{`
        html { scroll-behavior: smooth; }
        .reveal-on-scroll { opacity: 0; transform: translateY(40px) scale(0.98); transition: all 1s cubic-bezier(0.16, 1, 0.3, 1); filter: blur(5px); will-change: transform, opacity, filter; }
        .reveal-on-scroll.is-visible { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        .delay-100 { transition-delay: 100ms; }
        .delay-200 { transition-delay: 200ms; }
        .delay-300 { transition-delay: 300ms; }
        .delay-400 { transition-delay: 400ms; }
        .page-view { display: none; opacity: 0; transition: opacity 0.5s ease-in-out; min-height: 100vh; }
        .page-view.active { display: block; opacity: 1; }
        .bg-noise { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 50; opacity: 0.05; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E"); }
        .dark .bg-noise { opacity: 0.03; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .mask-linear-gradient { mask-image: linear-gradient(90deg, transparent 0%, black 10%, black 90%, transparent 100%); }
        .animate-marquee { animation: marquee 40s linear infinite; }
        @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
        .bg-canvas { background-color: #f8fafc; }
        .text-obsidian { color: #0f172a; }
        .text-subtle { color: #64748b; }
        .border-border { border-color: #e2e8f0; }
        .border-border\\/60 { border-color: rgba(226, 232, 240, 0.6); }
        .bg-border\\/60 { background-color: rgba(226, 232, 240, 0.6); }
        .bg-obsidian { background-color: #0f172a; }
      `}</style>

      <div className="bg-noise" />

      <div className="fixed top-0 left-0 w-full h-[120vh] -z-10 overflow-hidden pointer-events-none transition-all duration-700">
        <div
          id="canvas-container"
          ref={containerRef}
          className="w-full h-full opacity-100 dark:opacity-80 transition-opacity duration-700"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-white/40 via-white/20 to-white/60 dark:from-black/80 dark:via-black/60 dark:to-black/90 pointer-events-none" />
      </div>

      <header
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300 backdrop-blur-sm border-b border-transparent"
        id="navbar"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <button
              type="button"
              onClick={() => route("home")}
              className="flex items-center gap-2 group z-50"
            >
              <span className="text-xl font-bold tracking-tight text-neutral-900 dark:text-white transition-colors">
                Elevia
              </span>
            </button>

            <div className="hidden md:flex items-center gap-1 bg-white/80 dark:bg-neutral-900/80 border border-neutral-200 dark:border-white/10 rounded-full px-2 py-1 shadow-sm backdrop-blur-md">
              {["home", "features", "pricing", "roadmap"].map((view) => (
                <button
                  key={view}
                  type="button"
                  onClick={() => route(view)}
                  className={`px-5 py-2 text-sm font-medium rounded-full transition-all ${
                    activeView === view
                      ? "text-emerald-600 dark:text-emerald-400 bg-neutral-100 dark:bg-white/10"
                      : "text-neutral-600 dark:text-white/70 hover:text-emerald-600 dark:hover:text-emerald-400"
                  }`}
                >
                  {view === "home"
                    ? "Accueil"
                    : view === "features"
                      ? "Usage"
                      : view === "pricing"
                        ? "Entrer"
                        : "Cadre"}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 z-50">
              <button
                type="button"
                onClick={toggleTheme}
                className="p-2 rounded-full text-neutral-500 hover:text-neutral-900 dark:text-white/60 dark:hover:text-white bg-white/50 dark:bg-white/5 hover:bg-neutral-200 dark:hover:bg-white/10 transition-all focus:outline-none ring-1 ring-neutral-200 dark:ring-white/10"
                aria-label="Toggle Theme"
              >
                {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              <button
                type="button"
                className="md:hidden p-2 text-neutral-600 dark:text-white/80"
                onClick={() => setMobileOpen((open) => !open)}
              >
                <Menu className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>

        <div
          id="mobile-menu"
          className={`md:hidden absolute top-full left-0 w-full bg-white/95 dark:bg-neutral-900/95 backdrop-blur-xl border-b border-neutral-200 dark:border-white/10 py-6 px-6 shadow-xl z-40 ${
            mobileOpen ? "block" : "hidden"
          }`}
        >
          <div className="flex flex-col gap-6">
            <button
              type="button"
              onClick={() => route("home")}
              className="text-lg font-medium text-neutral-600 dark:text-white/70 text-left"
            >
              Accueil
            </button>
            <button
              type="button"
              onClick={() => route("features")}
              className="text-lg font-medium text-neutral-600 dark:text-white/70 text-left"
            >
              Usage
            </button>
            <button
              type="button"
              onClick={() => route("pricing")}
              className="text-lg font-medium text-neutral-600 dark:text-white/70 text-left"
            >
              Entrer
            </button>
            <button
              type="button"
              onClick={() => route("roadmap")}
              className="text-lg font-medium text-neutral-600 dark:text-white/70 text-left"
            >
              Cadre
            </button>
          </div>
        </div>
      </header>

      <main className="flex-grow pt-24 min-h-screen z-10">
        <div id="home" className={`page-view ${activeView === "home" ? "active" : ""}`}>
          <section className="relative pt-12 pb-24 sm:pt-24 sm:pb-32 px-6 text-center max-w-5xl mx-auto">
            <div className="reveal-on-scroll is-visible">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold uppercase tracking-wide mb-8 hover:bg-emerald-500/20 transition-colors cursor-default">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                Outil personnel, pas un raccourci
              </div>
              <h1 className="text-5xl sm:text-7xl md:text-8xl tracking-tighter font-semibold text-neutral-900 dark:text-white mb-8 leading-[1.1]">
                Postuler avec clarté.
                <br className="hidden sm:block" /> Sans fatigue inutile.
              </h1>
              <p className="text-lg sm:text-xl text-neutral-600 dark:text-white/60 max-w-2xl mx-auto mb-12 font-light leading-relaxed">
                Elevia est un outil personnel pour décider à quelles offres candidater, préparer tes candidatures plus
                vite, et garder une vue claire sur ce que tu as fait.
              </p>
              <div className="relative h-[280px] w-full max-w-2xl mx-auto mb-0 group mt-12">
                <div className="absolute left-1/2 top-0 w-44 h-56 rounded-xl border dark:border-white/10 bg-gradient-to-br dark:from-zinc-900 dark:to-zinc-950 shadow-xl transform -translate-x-[200%] rotate-[-12deg] transition-all duration-700 ease-out group-hover:-translate-x-[220%] group-hover:rotate-[-16deg] flex items-center justify-center overflow-hidden border-zinc-200 from-zinc-50 to-zinc-100">
                  <div className="w-full p-4 space-y-2 opacity-60">
                    <div className="text-xs font-semibold text-zinc-800 dark:text-white">24 offres analysées</div>
                    <div className="text-[10px] text-zinc-500 dark:text-white/50">3 pertinentes</div>
                    <div className="h-2 w-1/2 dark:bg-white/20 rounded-full bg-zinc-300"></div>
                    <div className="h-2 w-full dark:bg-white/10 rounded-full bg-zinc-200"></div>
                    <div className="h-2 w-3/4 dark:bg-white/10 rounded-full bg-zinc-200"></div>
                  </div>
                </div>
                <div className="absolute left-1/2 top-0 w-44 h-56 rounded-xl border dark:border-white/10 dark:bg-[#0A0A0A] shadow-xl transform -translate-x-[130%] rotate-[-6deg] transition-all duration-700 ease-out group-hover:-translate-x-[140%] group-hover:rotate-[-8deg] flex flex-col items-center justify-center z-10 border-zinc-200 bg-white">
                  <div className="w-12 h-12 rounded-full border dark:bg-yellow-500/10 dark:border-yellow-500/20 flex items-center justify-center mb-3 border-yellow-100 bg-yellow-50">
                  <div className="text-xs font-semibold text-yellow-700">Validée ✓</div>
                </div>
                <div className="text-xs font-medium text-zinc-800 dark:text-white">Éligibilité V.I.E</div>
                <div className="text-[10px] text-zinc-500 dark:text-white/50 mt-2">Âge · Nationalité · Diplôme</div>
              </div>
              <div className="absolute left-1/2 top-0 w-44 h-56 rounded-xl border dark:border-white/10 dark:bg-white shadow-xl transform -translate-x-[60%] rotate-[0deg] transition-all duration-700 ease-out group-hover:scale-105 z-20 flex flex-col items-start justify-between border-zinc-200 bg-zinc-900 p-4">
                <div className="text-xs text-white/70">Match 88 %</div>
                <div className="text-white font-semibold text-sm leading-tight">Analyste financier — V.I.E</div>
                <div className="text-[10px] text-white/60">Paris · Finance</div>
                <div className="text-[10px] text-emerald-300">+ SAP · Excel</div>
              </div>
              <div className="absolute left-1/2 top-0 w-44 h-56 rounded-xl border dark:border-white/10 bg-[#E0F2FE] dark:bg-[#0c2d48] shadow-xl transform translate-x-[10%] rotate-[6deg] transition-all duration-700 ease-out group-hover:translate-x-[20%] group-hover:rotate-[8deg] flex items-center justify-center z-10 overflow-hidden border-zinc-200">
                <div className="p-4 text-left w-full">
                  <div className="text-xs text-sky-700 dark:text-sky-200 font-semibold">Pourquoi ça matche</div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-white mt-2">Compétences alignées</div>
                  <div className="text-[10px] text-slate-600 dark:text-white/60">
                    Analyse · Reporting · Environnement international
                  </div>
                </div>
              </div>
              <div className="absolute left-1/2 top-0 w-44 h-56 rounded-xl border dark:border-white/10 bg-gradient-to-b dark:from-emerald-950/30 dark:to-black shadow-xl transform translate-x-[80%] rotate-[12deg] transition-all duration-700 ease-out group-hover:translate-x-[100%] group-hover:rotate-[16deg] flex items-center justify-center border-zinc-200 from-emerald-50 to-white">
                <div className="grid grid-cols-1 gap-2 p-4 text-left">
                  <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Candidature prête</div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">en 45 secondes</div>
                  <div className="text-[10px] text-slate-600 dark:text-white/60">CV + message générés</div>
                </div>
              </div>
              </div>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <button
                  type="button"
                  onClick={() => route("pricing")}
                  className="w-full sm:w-auto group relative inline-flex items-center justify-center bg-neutral-900 dark:bg-white text-white dark:text-black h-14 px-8 rounded-full text-sm font-semibold transition-all hover:scale-105 hover:shadow-xl hover:shadow-emerald-500/20"
                >
                  <span>Ouvrir Elevia</span>
                  <ChevronRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </button>
              </div>
            </div>
          </section>

          <section className="py-16 px-6 max-w-6xl mx-auto">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="group bg-white border border-slate-100 rounded-[2rem] p-5 shadow-sm hover:shadow-lg transition-all flex flex-col h-full">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
                        V.I.E
                      </span>
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                        Score · 78%
                      </span>
                    </div>

                    <h3 className="mt-3 text-base font-bold text-slate-900 leading-tight truncate">
                      Data Analyst
                    </h3>

                    <div className="mt-1 text-xs text-slate-500 truncate">
                      <span className="font-medium text-slate-700">DataBridge</span>
                      · Paris, France
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">
                      Match fort sur analyse de données & reporting (preuves dans ton profil).
                    </p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">Niveau d’études aligné (bac+5 requis / bac+5 profil).</p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">
                      ROME lié : Analyste data (référentiel FT) — compétences proches.
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · SQL
                  </span>
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · Power BI
                  </span>
                </div>

                <div className="mt-auto pt-5 flex flex-wrap items-center gap-2">
                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition">
                    Générer CV + LM
                  </button>

                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                    Shortlist
                  </button>

                  <button className="ml-auto px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-50 border border-slate-100 text-slate-600 hover:bg-slate-100 transition">
                    Ouvrir
                  </button>
                </div>
              </div>

              <div className="group bg-white border border-slate-100 rounded-[2rem] p-5 shadow-sm hover:shadow-lg transition-all flex flex-col h-full">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
                        V.I.E
                      </span>
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                        Score · 82%
                      </span>
                    </div>

                    <h3 className="mt-3 text-base font-bold text-slate-900 leading-tight truncate">
                      Développeur Full Stack
                    </h3>

                    <div className="mt-1 text-xs text-slate-500 truncate">
                      <span className="font-medium text-slate-700">NovaStack</span>
                      · Berlin, Allemagne
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">React + Node présents dans ton profil, match direct.</p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">Expérience internationale déjà mentionnée.</p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">ROME lié : Développeur web (compétences proches).</p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · CI/CD
                  </span>
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · AWS
                  </span>
                </div>

                <div className="mt-auto pt-5 flex flex-wrap items-center gap-2">
                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition">
                    Générer CV + LM
                  </button>

                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                    Shortlist
                  </button>

                  <button className="ml-auto px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-50 border border-slate-100 text-slate-600 hover:bg-slate-100 transition">
                    Ouvrir
                  </button>
                </div>
              </div>

              <div className="group bg-white border border-slate-100 rounded-[2rem] p-5 shadow-sm hover:shadow-lg transition-all flex flex-col h-full">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
                        V.I.E
                      </span>
                      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                        Score · 74%
                      </span>
                    </div>

                    <h3 className="mt-3 text-base font-bold text-slate-900 leading-tight truncate">
                      Commercial Export
                    </h3>

                    <div className="mt-1 text-xs text-slate-500 truncate">
                      <span className="font-medium text-slate-700">GlobeTrade</span>
                      · Shanghai, Chine
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">CRM + négociation alignés avec ton profil.</p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">Langue requise : anglais OK.</p>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-slate-700">
                    <Check className="mt-0.5 w-4 h-4 text-emerald-500 shrink-0" />
                    <p className="line-clamp-2">ROME lié : Commercial export (référentiel FT).</p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · Mandarin
                  </span>
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-rose-50/60 text-rose-700 border border-rose-100/60">
                    À renforcer · SAP
                  </span>
                </div>

                <div className="mt-auto pt-5 flex flex-wrap items-center gap-2">
                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition">
                    Générer CV + LM
                  </button>

                  <button className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                    Shortlist
                  </button>

                  <button className="ml-auto px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-50 border border-slate-100 text-slate-600 hover:bg-slate-100 transition">
                    Ouvrir
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="border-y border-neutral-200/50 dark:border-white/5 py-12 overflow-hidden bg-neutral-50/50 dark:bg-transparent">
            <div className="max-w-7xl mx-auto px-6 mb-8 text-center">
              <p className="text-xs font-semibold uppercase tracking-widest text-neutral-500 dark:text-white/40">
                Sources &amp; référentiels utilisés
              </p>
            </div>

            <div className="relative flex overflow-hidden mask-linear-gradient">
              <div className="flex animate-marquee whitespace-nowrap min-w-full shrink-0 items-center justify-around gap-16 px-8">
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Inbox className="w-6 h-6 text-emerald-500" /> France Travail
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Target className="w-6 h-6 text-emerald-500" /> Business France
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Compass className="w-6 h-6 text-emerald-500" /> ROME métiers
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Sparkles className="w-6 h-6 text-emerald-500" /> ESCO skills
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Send className="w-6 h-6 text-emerald-500" /> Catalogue VIE
                </div>
              </div>
              <div className="flex animate-marquee whitespace-nowrap min-w-full shrink-0 items-center justify-around gap-16 px-8">
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Inbox className="w-6 h-6 text-emerald-500" /> France Travail
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Target className="w-6 h-6 text-emerald-500" /> Business France
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Compass className="w-6 h-6 text-emerald-500" /> ROME métiers
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Sparkles className="w-6 h-6 text-emerald-500" /> ESCO skills
                </div>
                <div className="flex items-center gap-3 text-neutral-500 dark:text-neutral-400 font-bold text-lg">
                  <Send className="w-6 h-6 text-emerald-500" /> Catalogue VIE
                </div>
              </div>

              <div className="absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-white dark:from-black to-transparent z-10" />
              <div className="absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-white dark:from-black to-transparent z-10" />
            </div>
          </section>

          <section className="py-28 bg-neutral-50/50 dark:bg-white/5 border-t border-neutral-200 dark:border-white/5">
            <div className="max-w-6xl mx-auto px-6">
              <div className="flex flex-col md:flex-row justify-between items-end mb-16 reveal-on-scroll">
                <div className="max-w-2xl">
                  <h2 className="text-sm font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-widest mb-3">
                    Le problème
                  </h2>
                  <h3 className="text-4xl sm:text-5xl font-semibold text-neutral-900 dark:text-white">
                    Le problème n&apos;est pas la compétence. C&apos;est la répétition.
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => route("features")}
                  className="hidden md:inline-flex items-center text-sm font-semibold text-neutral-900 dark:text-white border-b border-neutral-300 dark:border-white/30 hover:border-emerald-500 pb-1 transition-colors"
                >
                  Voir la méthode <ChevronRight className="ml-2 w-4 h-4" />
                </button>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                <div className="p-8 rounded-3xl bg-white dark:bg-black border border-neutral-100 dark:border-white/10 shadow-xl shadow-neutral-200/50 dark:shadow-black/50 reveal-on-scroll delay-100">
                  <h4 className="text-xl font-bold text-neutral-900 dark:text-white mb-4">Ce qui fatigue</h4>
                  <ul className="space-y-3 text-neutral-600 dark:text-white/60">
                    <li className="flex gap-3">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Réécrire des messages similaires
                    </li>
                    <li className="flex gap-3">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Adapter le CV à chaque offre
                    </li>
                    <li className="flex gap-3">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Oublier où tu as postulé
                    </li>
                    <li className="flex gap-3">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Ne plus savoir quand relancer
                    </li>
                  </ul>
                </div>
                <div className="p-8 rounded-3xl bg-white dark:bg-black border border-neutral-100 dark:border-white/10 shadow-xl shadow-neutral-200/50 dark:shadow-black/50 reveal-on-scroll delay-200">
                  <h4 className="text-xl font-bold text-neutral-900 dark:text-white mb-4">Ce que ça crée</h4>
                  <p className="text-neutral-500 dark:text-white/60 leading-relaxed">
                    Ce n&apos;est pas difficile. C&apos;est usant. Tu perds du temps, tu doutes, et tu n&apos;as plus une vision claire
                    de ce qui a été envoyé.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section id="decision-lifecycle" className="relative w-full bg-canvas border-b border-border/60" style={{ height: "400vh" }}>
            <div className="sticky top-0 left-0 w-full h-screen overflow-hidden flex flex-col items-center justify-center">
              <div className="absolute inset-0 bg-[radial-gradient(#00000008_1px,transparent_1px)] [background-size:24px_24px] pointer-events-none"></div>
              <div className="max-w-4xl w-full px-6 md:px-12 relative z-10 flex flex-col items-center h-full py-20">
                <div className="text-center mb-12 shrink-0 opacity-0 transition-opacity duration-700" id="lifecycle-header">
                  <h2 className="font-sans text-2xl md:text-3xl font-semibold text-obsidian tracking-tight mb-3">
                    Pipeline Elevia
                  </h2>
                  <p className="text-subtle text-sm max-w-md mx-auto">
                    Simple, court, sans automatisme caché.
                  </p>
                </div>
                <div className="relative w-full max-w-2xl flex-1 flex flex-col justify-center my-auto">
                  <div className="absolute left-1/2 top-4 bottom-4 w-px bg-border/60 -translate-x-1/2"></div>
                  <div id="lifecycle-line" className="absolute left-1/2 top-4 w-px bg-obsidian -translate-x-1/2 transition-all duration-75 ease-linear h-0 max-h-[calc(100%-2rem)]"></div>
                  <div className="space-y-16 py-8 relative">
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.1">
                      <div className="w-[42%] text-right pr-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          01 Profil
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          Point de départ
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Tu poses ton contexte.
                        </p>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <div className="bg-white border border-border p-3 rounded shadow-sm inline-block">
                          <div className="flex items-center gap-2">
                            <span className="text-subtle text-xs">?</span>
                            <span className="text-xs font-medium text-obsidian">
                              Quel poste est cohérent pour moi ?
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.25">
                      <div className="w-[42%] text-right pr-8">
                        <div className="bg-white border border-border p-3 rounded shadow-sm inline-block text-left">
                          <span className="text-[10px] text-subtle block mb-1">
                            Filtre
                          </span>
                          <span className="text-xs font-medium text-obsidian">
                            Offres pertinentes uniquement
                          </span>
                        </div>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          02 Offres
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          Sélection claire
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Tu gardes le focus.
                        </p>
                      </div>
                    </div>
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.4">
                      <div className="w-[42%] text-right pr-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          03 Préparation
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          Brouillon + CV
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Ajustements ciblés.
                        </p>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <div className="bg-white border border-border p-3 rounded shadow-sm inline-flex items-center gap-3">
                          <div className="w-8 h-8 bg-slate-50 rounded flex items-center justify-center border border-border/50">
                            <span className="text-subtle text-xs">↗</span>
                          </div>
                          <div>
                            <div className="text-[10px] text-subtle">
                              Ajustement CV
                            </div>
                            <div className="text-xs font-bold text-obsidian">
                              + mots-clés pertinents
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.55">
                      <div className="w-[42%] text-right pr-8">
                        <div className="bg-white border border-border p-3 rounded shadow-sm inline-block max-w-[200px] text-left">
                          <div className="flex gap-1 mb-1">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                            <div className="w-1.5 h-1.5 rounded-full bg-border"></div>
                          </div>
                          <span className="text-xs font-medium text-obsidian">
                            Candidature prête, décision claire.
                          </span>
                        </div>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          04 Suivi
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          Historique
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Tu sais où tu en es.
                        </p>
                      </div>
                    </div>
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.7">
                      <div className="w-[42%] text-right pr-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          05 Relance
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          J+7, J+14
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Rien n’est oublié.
                        </p>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-obsidian text-white text-xs font-semibold shadow-lg shadow-obsidian/20">
                          <span>Relance envoyée</span>
                          <span className="text-xs">✔</span>
                        </span>
                      </div>
                    </div>
                    <div className="lifecycle-step group flex items-center justify-between w-full opacity-30 transition-all duration-500" data-threshold="0.85">
                      <div className="w-[42%] text-right pr-8">
                        <span className="font-mono text-[10px] text-subtle bg-slate-100 px-2 py-1 rounded inline-block">
                          ID: 8f2a...9c1
                        </span>
                      </div>
                      <div className="relative shrink-0 z-10">
                        <div className="w-3 h-3 rounded-full border border-border bg-canvas group-[.active]:border-obsidian group-[.active]:bg-obsidian transition-colors duration-300"></div>
                      </div>
                      <div className="w-[42%] pl-8">
                        <span className="font-mono text-[10px] text-subtle uppercase tracking-wider block mb-1">
                          06 Trace
                        </span>
                        <h3 className="font-sans text-base font-semibold text-obsidian">
                          Historique stable
                        </h3>
                        <p className="text-xs text-subtle mt-1 hidden md:block">
                          Tout reste clair.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="py-24 bg-neutral-900 text-white relative overflow-hidden">
            <div className="absolute inset-0 bg-emerald-900/10" />
            <div className="max-w-6xl mx-auto px-6 relative z-10">
              <div className="text-center mb-12 reveal-on-scroll">
                <h2 className="text-3xl sm:text-5xl font-semibold mb-6">Ce que Elevia ne fait pas</h2>
                <p className="text-xl text-neutral-400 max-w-2xl mx-auto">
                  Important : pas de promesses, pas d&apos;automatisation de tes décisions.
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                {[
                  "Ne postule pas à ta place",
                  "Ne garantit aucun résultat",
                  "N'automatise pas tes décisions",
                  "Ne remplace pas ton jugement",
                ].map((item, index) => (
                  <div
                    key={item}
                    className={`p-6 rounded-2xl border border-white/10 bg-white/5 reveal-on-scroll ${
                      index % 2 === 0 ? "delay-100" : "delay-200"
                    }`}
                  >
                    <p className="text-neutral-200 text-sm">{item}</p>
                  </div>
                ))}
              </div>

              <div className="mt-12 text-center text-neutral-400">
                C&apos;est un outil. Pas un raccourci.
              </div>
            </div>
          </section>

          <section className="py-28 px-6 max-w-5xl mx-auto text-center">
            <div className="reveal-on-scroll">
              <h2 className="text-4xl sm:text-6xl font-semibold text-neutral-900 dark:text-white mb-6">
                Une façon plus calme de candidater.
              </h2>
              <p className="text-xl text-neutral-600 dark:text-white/60 mb-10">
                Commencer avec ton profil. Une offre à la fois.
              </p>
              <button
                type="button"
                onClick={() => route("pricing")}
                className="group inline-flex items-center justify-center bg-emerald-500 text-white h-16 px-10 rounded-full text-lg font-semibold shadow-lg shadow-emerald-500/30 transition-all hover:bg-emerald-600 hover:scale-105"
              >
                Entrer dans l&apos;espace
                <ChevronRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </section>
        </div>

        <div id="features" className={`page-view ${activeView === "features" ? "active" : ""}`}>
          <section className="pt-32 pb-20 px-6 max-w-6xl mx-auto">
            <div className="text-center max-w-3xl mx-auto mb-16 reveal-on-scroll">
              <h1 className="text-5xl sm:text-6xl font-bold text-neutral-900 dark:text-white mb-6">
                Le flux Elevia
              </h1>
              <p className="text-xl text-neutral-600 dark:text-white/60">
                Un tunnel clair, sans surprise. Tu gardes la main du début à la fin.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              {[
                {
                  title: "1. Définir ton profil",
                  text: "Tu poses ton cadre : compétences, langues, préférences pays.",
                  icon: <Compass className="w-6 h-6" />,
                },
                {
                  title: "2. Choisir une offre",
                  text: "Tu vois ce qui correspond, sans bruit parasite.",
                  icon: <Target className="w-6 h-6" />,
                },
                {
                  title: "3. Préparer la candidature",
                  text: "Brouillon de message + ajustements CV ciblés.",
                  icon: <FileText className="w-6 h-6" />,
                },
                {
                  title: "4. Suivre l&apos;envoi",
                  text: "État, relances, historique clair.",
                  icon: <Inbox className="w-6 h-6" />,
                },
              ].map((step, index) => (
                <div
                  key={step.title}
                  className={`p-8 rounded-3xl bg-neutral-50 dark:bg-white/5 border border-neutral-200 dark:border-white/10 hover:border-emerald-500/50 transition-all duration-300 reveal-on-scroll ${
                    index % 2 === 0 ? "delay-100" : "delay-200"
                  }`}
                >
                  <div className="w-12 h-12 bg-emerald-500/10 rounded-lg flex items-center justify-center mb-6 text-emerald-500">
                    {step.icon}
                  </div>
                  <h3 className="text-xl font-semibold text-neutral-900 dark:text-white mb-3">{step.title}</h3>
                  <p className="text-neutral-600 dark:text-white/60 text-sm leading-relaxed mb-6">{step.text}</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div id="pricing" className={`page-view ${activeView === "pricing" ? "active" : ""}`}>
          <section className="pt-32 pb-20 px-6 max-w-6xl mx-auto">
            <div className="text-center max-w-3xl mx-auto mb-16 reveal-on-scroll">
              <h1 className="text-5xl sm:text-6xl font-bold text-neutral-900 dark:text-white mb-6">
                Entrer dans Elevia
              </h1>
              <p className="text-xl text-neutral-600 dark:text-white/60">
                Choisis ton rythme. Pas de promesse, juste un cadre clair.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-10 max-w-4xl mx-auto">
              <div className="rounded-3xl border border-neutral-200 dark:border-white/10 bg-neutral-50 dark:bg-white/5 p-10 reveal-on-scroll">
                <h3 className="text-2xl font-bold text-neutral-900 dark:text-white mb-2">Accès personnel</h3>
                <div className="text-neutral-500 mb-8">Commencer seul, une offre à la fois.</div>
                <button
                  type="button"
                  className="w-full py-4 rounded-xl border border-neutral-300 dark:border-white/20 hover:bg-neutral-200 dark:hover:bg-white/10 transition-colors font-semibold"
                >
                  Ouvrir Elevia
                </button>
                <div className="mt-8 space-y-4 text-sm text-neutral-600 dark:text-white/60">
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Clarifier les offres pertinentes
                  </div>
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Préparer un brouillon propre
                  </div>
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Suivre tes candidatures
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border-2 border-emerald-500 bg-neutral-900 dark:bg-black p-10 relative reveal-on-scroll delay-100">
                <div className="absolute top-0 right-0 bg-emerald-500 text-white px-4 py-1 rounded-bl-xl rounded-tr-2xl text-xs font-bold uppercase">
                  Option guidée
                </div>
                <h3 className="text-2xl font-bold text-white mb-2">Parcours accompagné</h3>
                <div className="text-neutral-400 mb-8">Un cadre plus structuré, même sobriété.</div>
                <button
                  type="button"
                  className="w-full py-4 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white transition-colors font-semibold shadow-lg shadow-emerald-500/30"
                >
                  Entrer dans l&apos;espace
                </button>
                <div className="mt-8 space-y-4 text-white text-sm">
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Cadre de candidature en 4 étapes
                  </div>
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Notes de relance centralisées
                  </div>
                  <div className="flex gap-3">
                    <Check className="w-5 h-5 text-emerald-500" /> Historique clair et stable
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <div id="roadmap" className={`page-view ${activeView === "roadmap" ? "active" : ""}`}>
          <section className="pt-32 pb-20 px-6 max-w-5xl mx-auto">
            <div className="text-center max-w-3xl mx-auto mb-16 reveal-on-scroll">
              <h1 className="text-5xl sm:text-6xl font-bold text-neutral-900 dark:text-white mb-6">
                Cadre de confiance
              </h1>
              <p className="text-xl text-neutral-600 dark:text-white/60">
                Ce qui est accepté, ce qui est interdit. Pour rester sur les rails.
              </p>
            </div>

            <div className="space-y-8">
              <div className="bg-neutral-50 dark:bg-white/5 border border-neutral-200 dark:border-white/10 rounded-2xl p-8 reveal-on-scroll">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-6">
                  <h3 className="text-2xl font-bold text-neutral-900 dark:text-white">Principes</h3>
                  <span className="inline-flex items-center px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 text-xs font-bold uppercase tracking-wide mt-2 sm:mt-0">
                    Stable
                  </span>
                </div>
                <ul className="space-y-3 text-neutral-600 dark:text-white/60">
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Pas d&apos;automatisation des décisions
                  </li>
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Pas de promesse de résultat
                  </li>
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Transparence sur les sources
                  </li>
                </ul>
              </div>

              <div className="bg-neutral-50 dark:bg-white/5 border border-neutral-200 dark:border-white/10 rounded-2xl p-8 reveal-on-scroll delay-100">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-6">
                  <h3 className="text-2xl font-bold text-neutral-900 dark:text-white">Objectif</h3>
                  <span className="inline-flex items-center px-3 py-1 rounded-full bg-neutral-100 dark:bg-white/10 text-neutral-500 dark:text-neutral-400 text-xs font-bold uppercase tracking-wide mt-2 sm:mt-0">
                    Focus
                  </span>
                </div>
                <ul className="space-y-3 text-neutral-600 dark:text-white/60">
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Réduire la fatigue de candidature
                  </li>
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Garder un historique clair
                  </li>
                  <li className="flex gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 mt-2" /> Rester maître de ses choix
                  </li>
                </ul>
              </div>
            </div>
          </section>
        </div>
      </main>

      <footer className="border-t border-neutral-200 dark:border-white/10 bg-white dark:bg-black py-16 relative z-10">
        <div className="max-w-7xl mx-auto px-6 grid gap-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-6">
              <span className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">Elevia</span>
            </div>
            <p className="text-sm text-neutral-500 dark:text-white/50 max-w-sm leading-relaxed mb-6">
              Un outil personnel pour garder un cadre clair quand tu postules. Pas de promesse. Juste de l&apos;ordre.
            </p>
          </div>
          <div>
            <h4 className="text-sm font-bold text-neutral-900 dark:text-white mb-6 uppercase tracking-wider">Produit</h4>
            <ul className="space-y-3 text-sm text-neutral-500 dark:text-white/60">
              <li>
                <button
                  type="button"
                  onClick={() => route("home")}
                  className="hover:text-emerald-500 transition-colors"
                >
                  Accueil
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => route("features")}
                  className="hover:text-emerald-500 transition-colors"
                >
                  Usage
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => route("pricing")}
                  className="hover:text-emerald-500 transition-colors"
                >
                  Entrer
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => route("roadmap")}
                  className="hover:text-emerald-500 transition-colors"
                >
                  Cadre
                </button>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-bold text-neutral-900 dark:text-white mb-6 uppercase tracking-wider">Contact</h4>
            <ul className="space-y-3 text-sm text-neutral-500 dark:text-white/60">
              <li>Entrer dans l&apos;espace</li>
              <li>Commencer avec ton profil</li>
            </ul>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-6 mt-16 pt-8 border-t border-neutral-200 dark:border-white/10">
          <p className="text-xs text-center text-neutral-400 dark:text-white/30">© 2026 Elevia</p>
        </div>
      </footer>

      <button
        type="button"
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        className={`fixed bottom-6 right-6 z-50 p-3 rounded-full bg-neutral-900 dark:bg-emerald-500 text-white dark:text-neutral-900 shadow-xl transition-all duration-300 hover:-translate-y-1 focus:outline-none ${
          showScrollTop ? "translate-y-0 opacity-100" : "translate-y-20 opacity-0"
        }`}
        aria-label="Scroll to top"
      >
        <ArrowUp className="w-5 h-5" />
      </button>

      <script type="x-shader/x-vertex" id="vertexShader">
        {`uniform float uTime; uniform float uDistortion; uniform float uSize; uniform vec2 uMouse; varying float vAlpha; varying vec3 vPos; varying float vNoise;
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; } vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; } vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); } vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; } float snoise(vec3 v) { const vec2 C = vec2(1.0/6.0, 1.0/3.0) ; const vec4 D = vec4(0.0, 0.5, 1.0, 2.0); vec3 i = floor(v + dot(v, C.yyy) ); vec3 x0 = v - i + dot(i, C.xxx) ; vec3 g = step(x0.yzx, x0.xyz); vec3 l = 1.0 - g; vec3 i1 = min( g.xyz, l.zxy ); vec3 i2 = max( g.xyz, l.zxy ); vec3 x1 = x0 - i1 + 1.0 * C.xxx; vec3 x2 = x0 - i2 + 2.0 * C.xxx; vec3 x3 = x0 - 1.0 + 3.0 * C.xxx; i = mod289(i); vec4 p = permute( permute( permute( i.z + vec4(0.0, i1.z, i2.z, 1.0 )) + i.y + vec4(0.0, i1.y, i2.y, 1.0 )) + i.x + vec4(0.0, i1.x, i2.x, 1.0 )); float n_ = 1.0/7.0; vec3 ns = n_ * D.wyz - D.xzx; vec4 j = p - 49.0 * floor(p * ns.z *ns.z); vec4 x_ = floor(j * ns.z); vec4 y_ = floor(j - 7.0 * x_ ); vec4 x = x_ *ns.x + ns.yyyy; vec4 y = y_ *ns.x + ns.yyyy; vec4 h = 1.0 - abs(x) - abs(y); vec4 b0 = vec4( x.xy, y.xy ); vec4 b1 = vec4( x.zw, y.zw ); vec4 s0 = floor(b0)*2.0 + 1.0; vec4 s1 = floor(b1)*2.0 + 1.0; vec4 sh = -step(h, vec4(0.0)); vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ; vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ; vec3 p0 = vec3(a0.xy,h.x); vec3 p1 = vec3(a0.zw,h.y); vec3 p2 = vec3(a1.xy,h.z); vec3 p3 = vec3(a1.zw,h.w); vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3))); p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w; vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0); m = m * m; return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) ); }
  void main() { vec3 pos = position; float noiseFreq = 0.5; float noiseAmp = uDistortion; float noise = snoise(vec3(pos.x * noiseFreq + uTime * 0.1, pos.y * noiseFreq, pos.z * noiseFreq)); vNoise = noise; vec3 newPos = pos + (normalize(pos) * noise * noiseAmp); float dist = distance(uMouse * 10.0, newPos.xy); float interaction = smoothstep(5.0, 0.0, dist); newPos += normalize(pos) * interaction * 0.5; vec4 mvPosition = modelViewMatrix * vec4(newPos, 1.0); gl_Position = projectionMatrix * mvPosition; gl_PointSize = uSize * (24.0 / -mvPosition.z) * (1.0 + noise * 0.5); vAlpha = 1.0; vPos = newPos; }`}
      </script>
      <script type="x-shader/x-fragment" id="fragmentShader">
        {`uniform vec3 uColor; uniform float uOpacity; varying float vNoise; varying vec3 vPos;
  void main() { vec2 center = gl_PointCoord - vec2(0.5); float dist = length(center); if (dist > 0.5) discard; float alpha = smoothstep(0.5, 0.2, dist) * uOpacity; vec3 darkColor = uColor * 0.5; vec3 lightColor = uColor * 1.8; vec3 finalColor = mix(darkColor, lightColor, vNoise * 0.5 + 0.5); gl_FragColor = vec4(finalColor, alpha); }`}
      </script>
    </div>
  );
}
