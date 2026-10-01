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

/**
 * What counts as a person's name — shared by registration, the profile, and the
 * affiliate form. Mirrors `check_person_name` in backend/app/schemas/_types.py,
 * and both are tested against the same cases (lib/__fixtures__/name-cases.json),
 * so the form never says yes where the API says no.
 *
 * Letters in any script, spaces, hyphens, apostrophes and periods: "Mary-Jane
 * O'Brien", "Smith Jr.", "J. R. R. Tolkien", "محمد علي". Digits, other symbols,
 * a lone letter, stray punctuation at the edges and a letter repeated four times
 * ("Aaaaaa") are not names.
 *
 * @returns the tidied name (outer space trimmed, inner runs collapsed).
 * @throws Error with a sentence the person can act on.
 */
export const PERSON_NAME_MAX = 100

const NAME_PUNCT = "-'\u2019."
const NAME_JOINERS = "-'\u2019"

export function validatePersonName(raw: string): string {
  const cleaned = (raw ?? '').split(/\s+/).filter(Boolean).join(' ')
  if (!cleaned) throw new Error('Enter your name.')

  const chars = [...cleaned]
  if (chars.some((c) => /\p{N}/u.test(c))) throw new Error("A name can't contain numbers.")
  if (chars.length > PERSON_NAME_MAX) {
    throw new Error(`That name is too long. Use ${PERSON_NAME_MAX} characters or fewer.`)
  }
  if (chars.filter((c) => /\p{L}/u.test(c)).length < 2) {
    throw new Error('That name is too short. Enter at least 2 letters.')
  }
  const allowed = (c: string) =>
    /\p{L}/u.test(c) || /\p{M}/u.test(c) || c === ' ' || NAME_PUNCT.includes(c) || c === '\u200c' || c === '\u200d'
  if (!chars.every(allowed)) throw new Error('Use letters, spaces, hyphens and apostrophes only.')

  const invalid = new Error("That doesn't look like a valid name.")
  if (NAME_PUNCT.includes(chars[0]) || NAME_JOINERS.includes(chars[chars.length - 1])) throw invalid
  for (let i = 0; i < chars.length - 1; i++) {
    const [left, right] = [chars[i], chars[i + 1]]
    if (NAME_PUNCT.includes(left) && NAME_PUNCT.includes(right)) throw invalid
    if (left === ' ' && NAME_PUNCT.includes(right)) throw invalid
  }
  if (/(.)\1{3,}/u.test(cleaned)) throw invalid
  return cleaned
}

const DISPLAY_NAME_FORBIDDEN = new Set('<>{}[]\\|^~`$%*=;"')

/**
 * A business or assistant name — "Acme Inc.", "3M", "Studio 54", "Aria".
 * Digits and ordinary punctuation are fine; it still has to be a name, so at
 * least one letter and two characters. Mirrors `check_display_name`.
 */
export function validateDisplayName(raw: string, label = 'name', maxLength = 100): string {
  const cleaned = (raw ?? '').split(/\s+/).filter(Boolean).join(' ')
  if (!cleaned) throw new Error(`Enter a ${label}.`)
  const chars = [...cleaned]
  if (chars.length > maxLength) {
    throw new Error(`That ${label} is too long. Use ${maxLength} characters or fewer.`)
  }
  if (chars.length < 2) throw new Error(`That ${label} is too short. Enter at least 2 characters.`)
  if (!chars.some((c) => /\p{L}/u.test(c))) throw new Error(`The ${label} needs at least one letter.`)
  if (chars.some((c) => DISPLAY_NAME_FORBIDDEN.has(c) || /\p{C}/u.test(c))) {
    throw new Error(`That ${label} contains characters that aren't allowed.`)
  }
  return cleaned
}

/** The message for an invalid value, or `undefined` when it is fine. */
export function personNameError(raw: string): string | undefined {
  try {
    validatePersonName(raw)
    return undefined
  } catch (err) {
    return (err as Error).message
  }
}

export function displayNameError(raw: string, label?: string, maxLength?: number): string | undefined {
  try {
    validateDisplayName(raw, label, maxLength)
    return undefined
  } catch (err) {
    return (err as Error).message
  }
}
