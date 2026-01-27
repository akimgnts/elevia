/**
 * Single global aurora background layer
 * Fixed position, behind all content with reduced opacity for Apple-clean aesthetic
 */
export function HeroVisualLayer() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="aurora-layer absolute -left-32 -top-32 h-[600px] w-[600px] rounded-full opacity-15 blur-3xl" />
      <div className="aurora-layer absolute -right-32 top-32 h-[500px] w-[500px] rounded-full opacity-10 blur-3xl" />
    </div>
  );
}
