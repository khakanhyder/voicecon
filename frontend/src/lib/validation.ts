/**
 * Shared field validators for user-facing forms.
 *
 * These answer immediately, in the browser. They are not the gate — the API
 * re-checks everything — but a form that accepts "dcsdcs" as a company website
 * and only reveals the problem later (as a dead link on the settings page) is
 * worse than one that says so while the cursor is still in the field.
 */

/** A hostname label: alphanumeric, inner hyphens allowed. */
const HOST_LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/

/**
 * Validate and canonicalise a website someone typed.
 *
 * Accepts what people actually type — `acme.com`, `www.acme.com`,
 * `https://acme.com/careers` — and returns it with a scheme attached so the
 * stored value is a link that works when clicked. Rejects a bare word with no
 * dot (`dcsdcs`), anything with whitespace, and any scheme other than http(s)
 * so a stored `javascript:` URL can never be rendered as an href.
 *
 * @returns the normalized URL, or `null` when the input is empty/whitespace.
 * @throws Error with a message written for the user when the input is invalid.
 */
export function normalizeWebsiteUrl(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null

  if (/\s/.test(trimmed)) {
    throw new Error('Enter a website address without spaces')
  }

  const hasScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)
  if (hasScheme && !/^https?:\/\//i.test(trimmed)) {
    throw new Error('Website must start with http:// or https://')
  }

  let url: URL
  try {
    url = new URL(hasScheme ? trimmed : `https://${trimmed}`)
  } catch {
    throw new Error('Enter a valid website, e.g. www.acme.com')
  }

  // `new URL()` is lenient by design — it happily parses "https://dcsdcs" as a
  // host. A real public website has at least one dot and an alphabetic TLD.
  const host = url.hostname.toLowerCase()
  const labels = host.split('.')
  const tld = labels[labels.length - 1]

  const looksLikeADomain =
    labels.length >= 2 &&
    labels.every((label) => HOST_LABEL.test(label)) &&
    /^[a-z]{2,}$/.test(tld)

  if (!looksLikeADomain) {
    throw new Error('Enter a valid website, e.g. www.acme.com')
  }

  url.hostname = host
  // A trailing slash on a bare domain is noise in a text field the user reads back.
  return url.pathname === '/' && !url.search && !url.hash
    ? `${url.protocol}//${host}`
    : url.toString()
}

/**
 * Check a phone number the user typed by hand.
 *
 * Deliberately loose: formatting varies by country and the dial code is picked
 * from a separate select, so this only rejects lengths no real subscriber
 * number has. Numbers bought through the carrier search skip this — they
 * arrive already in E.164.
 */
export function isPlausiblePhoneNumber(raw: string): boolean {
  const digits = raw.replace(/\D/g, '')
  return digits.length >= 7 && digits.length <= 15
}
