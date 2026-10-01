/**
 * Shared field validators for user-facing forms.
 *
 * These answer immediately, in the browser. They are not the gate — the API
 * re-checks everything — but a form that accepts "dcsdcs" as a company website
 * and only reveals the problem later (as a dead link on the settings page) is
 * worse than one that says so while the cursor is still in the field.
 */

import { TLDS } from './tlds'

/** A hostname label: alphanumeric, inner hyphens allowed. */
const HOST_LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/

/**
 * Validate and canonicalise a website someone typed.
 *
 * Accepts what people actually type — `acme.com`, `www.acme.com`,
 * `https://acme.com/careers` — and returns it with a scheme attached so the
 * stored value is a link that works when clicked. Rejects a bare word with no
 * dot (`dcsdcs`), an ending that is not a real top-level domain
 * (`as.asdfdsf`), anything with whitespace, and any scheme other than http(s)
 * so a stored `javascript:` URL can never be rendered as an href. Whether the
 * domain is actually registered is the API's check: it needs a DNS lookup.
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
  // host. A real public website has at least one dot and ends in a TLD that
  // exists; "any letters" accepted endings nobody can register.
  const host = url.hostname.toLowerCase()
  const labels = host.split('.')
  const tld = labels[labels.length - 1]

  const looksLikeADomain =
    labels.length >= 2 &&
    labels.every((label) => HOST_LABEL.test(label)) &&
    TLDS.has(tld)

  if (!looksLikeADomain) {
    throw new Error('Enter a valid website, e.g. www.acme.com')
  }

  url.hostname = host
  // A trailing slash on a bare domain is noise in a text field the user reads back.
  return url.pathname === '/' && !url.search && !url.hash
    ? `${url.protocol}//${host}`
    : url.toString()
}
