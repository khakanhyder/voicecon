'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

interface ModalOverlayProps {
  /** Called on Escape and on a press on the backdrop. */
  onClose: () => void
  children: ReactNode
  /** Blocks Escape / backdrop close while something is in flight. */
  busy?: boolean
  /** False for forms that would lose typed input to a stray click outside. */
  closeOnBackdrop?: boolean
  /** `top` for palettes that should not jump as their results change height. */
  align?: 'center' | 'top'
  /** Backdrop colour / blur and z-index. */
  className?: string
  /** Padding and alignment of the area the panel sits in. */
  innerClassName?: string
}

/**
 * The backdrop every modal sits on.
 *
 * Two things each hand-rolled `fixed inset-0` overlay got wrong:
 *
 * - **Rendered in place.** The dashboard has transformed ancestors, which turn
 *   `position: fixed` into "relative to that ancestor" — the overlay then
 *   covers only part of the screen and the dialog is cut off. This renders
 *   into <body>, where `fixed` means the viewport.
 * - **Centred with flex inside a fixed box.** A panel taller than the screen
 *   overflows equally above and below, and the part above can never be
 *   scrolled to. Here the backdrop scrolls and the panel is centred inside a
 *   `min-h-full` box, so a tall panel starts at the top and scrolls instead.
 *
 * It also locks the page scroll, closes on Escape and gives focus back to
 * whatever opened it. The panel itself (role="dialog", its width, its look) is
 * the caller's.
 */
export function ModalOverlay({
  onClose,
  children,
  busy = false,
  closeOnBackdrop = true,
  align = 'center',
  className,
  innerClassName,
}: ModalOverlayProps) {
  const [mounted, setMounted] = useState(false)

  // Latest values without re-running the effect below on every render.
  const onCloseRef = useRef(onClose)
  const busyRef = useRef(busy)
  onCloseRef.current = onClose
  busyRef.current = busy

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    if (!mounted) return
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busyRef.current) onCloseRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKey)
      previousFocus?.focus?.()
    }
  }, [mounted])

  if (!mounted) return null

  // Only a press that both starts and ends on the backdrop dismisses: a drag
  // that begins in a text field and drifts outside must not close the dialog.
  const onBackdrop = (e: React.MouseEvent) => {
    if (closeOnBackdrop && !busy && e.target === e.currentTarget) onClose()
  }

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-slate-900/50',
        className,
      )}
    >
      <div
        onMouseDown={onBackdrop}
        className={cn(
          'flex min-h-full justify-center p-4',
          align === 'top' ? 'items-start' : 'items-center',
          innerClassName,
        )}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
