export function HeroVisualLayer() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="aurora-layer absolute -left-24 -top-24 h-[520px] w-[520px] rounded-full blur-3xl" />
      <div className="aurora-layer absolute right-[-120px] top-24 h-[520px] w-[520px] rounded-full blur-3xl" />
      <div className="absolute inset-0 bg-gradient-to-b from-white/60 via-white/40 to-white/70" />
    </div>
  );
}
