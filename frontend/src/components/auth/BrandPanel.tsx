'use client'

import { useRef } from 'react'
import Image from 'next/image'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { BRAND_CHIP, BRAND_STAGE, BrandPanelIcons, RobotIllustration } from '@/lib/icons'

/**
 * The illustration panel shown on the right of every onboarding / auth screen
 * (sign in, sign up, company details, pricing, billing).
 *
 * Reusable: drop it into any onboarding page's layout. Optional `caption`
 * lets a page add supporting copy beneath the robot.
 *
 * Motion (GSAP): a one-shot entrance timeline (glow → robot pop → connectors →
 * chips stagger) hands off to a gentle ambient loop — robot float, chip
 * parallax, breathing glow, and dashes that flow toward the robot. Initial
 * hidden states are applied imperatively in `useGSAP` (which runs before paint)
 * so there's no flash, and a no-JS / reduced-motion visitor still sees the full
 * static scene.
 */
export function BrandPanel({ caption }: { caption?: React.ReactNode }) {
  const root = useRef<HTMLDivElement>(null)

  useGSAP(
    () => {
      const reduce =
        typeof window !== 'undefined' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches

      // Re-center the glow & robot via GSAP so its matrix owns the transform
      // (the Tailwind -translate classes are the no-JS fallback only).
      gsap.set(['.bp-glow', '.bp-robot'], {
        xPercent: -50,
        yPercent: -50,
        transformOrigin: '50% 50%',
      })
      gsap.set('.bp-chip', { transformOrigin: '50% 50%' })

      if (reduce) return // honour reduced-motion: leave the static scene as-is.

      // ── Entrance ───────────────────────────────────────────────────────
      gsap.set('.bp-glow', { scale: 0.6, opacity: 0 })
      gsap.set('.bp-ring', { opacity: 0 })
      gsap.set('.bp-robot', { y: 30, opacity: 0, scale: 0.85 })
      gsap.set('.bp-connector', { opacity: 0 })
      gsap.set('.bp-chip', { scale: 0, opacity: 0 })

      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

      tl.to('.bp-glow', { scale: 1, opacity: 1, duration: 1.1 })
        .to('.bp-ring', { opacity: 1, duration: 0.8 }, '-=0.9')
        .to(
          '.bp-robot',
          { y: 0, opacity: 1, scale: 1, duration: 0.9, ease: 'back.out(1.5)' },
          '-=0.6'
        )
        .to('.bp-connector', { opacity: 1, duration: 0.5 }, '-=0.4')
        .to(
          '.bp-chip',
          {
            scale: 1,
            opacity: 1,
            duration: 0.6,
            ease: 'back.out(1.7)',
            stagger: { each: 0.12, from: 'random' },
          },
          '-=0.3'
        )

      // ── Ambient loop (starts once the entrance settles) ──────────────────
      tl.add(() => {
        // Robot: gentle vertical float.
        gsap.to('.bp-robot', {
          y: '-=12',
          duration: 3,
          ease: 'sine.inOut',
          repeat: -1,
          yoyo: true,
        })

        // Chips: soft parallax — each drifts with its own phase & distance.
        gsap.utils.toArray<HTMLElement>('.bp-chip').forEach((chip, i) => {
          gsap.to(chip, {
            y: i % 2 === 0 ? '-=10' : '+=10',
            duration: 2.6 + i * 0.4,
            ease: 'sine.inOut',
            repeat: -1,
            yoyo: true,
            delay: i * 0.2,
          })
        })

        // Glow: slow breathing pulse.
        gsap.to('.bp-glow', {
          scale: 1.06,
          opacity: 0.85,
          duration: 4,
          ease: 'sine.inOut',
          repeat: -1,
          yoyo: true,
        })

        // Connectors: march the dashes toward the robot (data streaming in).
        gsap.to('.bp-connector', {
          strokeDashoffset: -14,
          duration: 1.2,
          ease: 'none',
          repeat: -1,
        })
      })
    },
    { scope: root }
  )

  return (
    <div
      ref={root}
      className="relative flex h-full min-h-[560px] w-full items-center justify-center overflow-hidden rounded-3xl"
      style={{
        background: 'linear-gradient(180deg, #213B50 0%, #175455 100%)',
      }}
    >
      <div className="relative flex flex-col items-center">
        {/* Subtle outer circle */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          // style={{ width: 640, height: 640, background: '#252943', opacity: 0.22 }}
        />
        {/* Teal center circle (Figma) */}
        <div
          className="bp-glow pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: 500,
            height: 500,
            background: 'linear-gradient(180deg, #28746B 0%, #175455 100%)',
            WebkitMaskImage: 'linear-gradient(180deg, black 0%, black 70%, transparent 100%)',
            maskImage: 'linear-gradient(180deg, black 0%, black 30%, transparent 100%)',
          }}
        />

        {/* Illustration stage — robot + chips + rings + connectors all share
            one 400×400 coordinate system so connectors line up exactly. */}
        <div className="relative z-10" style={{ width: BRAND_STAGE, height: BRAND_STAGE }}>
          {/* concentric rings + dashed connectors */}
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox={`0 0 ${BRAND_STAGE} ${BRAND_STAGE}`}
            fill="none"
          >
            <circle
              className="bp-ring"
              cx="200"
              cy="200"
              r="196"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="1"
            />
            {BrandPanelIcons.map(({ key, connector }) => (
              <path
                key={key}
                className="bp-connector"
                d={connector}
                stroke="rgba(255,255,255,0.28)"
                strokeWidth="1.5"
                strokeDasharray="2 5"
                strokeLinecap="round"
              />
            ))}
          </svg>

          {/* center robot */}
          <div className="bp-robot absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <RobotIllustration className="h-auto w-[200px] drop-shadow-2xl" />
          </div>

          {/* integration chips */}
          {BrandPanelIcons.map(({ key, src, alt, cx, cy }) => (
            <div
              key={key}
              className="bp-chip absolute drop-shadow-lg"
              style={{
                left: cx - BRAND_CHIP / 2,
                top: cy - BRAND_CHIP / 2,
                width: BRAND_CHIP,
                height: BRAND_CHIP,
              }}
            >
              <Image
                src={src}
                alt={alt}
                width={BRAND_CHIP}
                height={BRAND_CHIP}
                className="h-full w-full"
              />
            </div>
          ))}
        </div>

        {caption && (
          <div className="-mt-2 max-w-xs px-6 text-center text-sm leading-relaxed text-white/80">
            {caption}
          </div>
        )}
      </div>
    </div>
  )
}
