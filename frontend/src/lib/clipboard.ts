/**
 * Copy text to the clipboard, and say truthfully whether it worked.
 *
 * `navigator.clipboard` only exists on a secure page (https or localhost), can
 * be refused by the browser, and returns a promise — calling it without
 * awaiting and then announcing "Copied" told people a secret was on their
 * clipboard when it was not. This awaits it, falls back to the older
 * selection-based copy where the modern API is missing or refused, and
 * resolves false when neither worked so the caller can say so.
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Refused (permissions, not focused, insecure context): try the fallback.
  }
  return legacyCopy(text)
}

function legacyCopy(text: string): boolean {
  if (typeof document === 'undefined') return false
  const area = document.createElement('textarea')
  area.value = text
  // Off-screen but still selectable; readonly keeps a phone keyboard closed.
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.top = '0'
  area.style.left = '-9999px'
  document.body.appendChild(area)
  const previous = document.activeElement as HTMLElement | null
  try {
    area.select()
    area.setSelectionRange(0, text.length)
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(area)
    previous?.focus?.()
  }
}
