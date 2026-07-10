/**
 * Decorative brand-gradient bar pinned to the bottom of the viewport on small
 * screens only. On lg+ the BrandPanel carries the brand colour, so the bar is
 * hidden there. Shared across every auth / onboarding screen (login, register,
 * company information, pricing, billing) so they match the Figma mobile design.
 */
export function MobileAccentBar() {
  return (
    <div
      aria-hidden
      className="fixed inset-x-0 bottom-0 z-50 h-[23px] lg:hidden bg-[#0F6A59]"
    />
  )
}
