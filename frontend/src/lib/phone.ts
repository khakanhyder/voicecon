/**
 * Phone numbers typed into a form: the country list, cleaning and validation.
 *
 * Validation uses libphonenumber-js, which knows every national numbering plan,
 * so "+92 300 1234567" passes and "abc" or a number a country cannot have does
 * not. The API checks again (backend `PhoneNumberStr`) and stores E.164, which
 * is also what `phoneToE164` produces.
 */
import {
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  type CountryCode,
} from 'libphonenumber-js/min'

export interface PhoneCountry {
  iso: CountryCode
  name: string
  /** Calling code with a leading "+", e.g. "+44". */
  dial: string
}

/** What a phone field holds: the picked country and the digits typed beside it. */
export interface PhoneValue {
  country: CountryCode
  national: string
}

export const DEFAULT_PHONE_COUNTRY: CountryCode = 'US'

function buildCountries(): PhoneCountry[] {
  let names: Intl.DisplayNames | null = null
  try {
    names = new Intl.DisplayNames(['en'], { type: 'region' })
  } catch {
    // Very old browsers: fall back to the ISO code as the name.
  }
  return getCountries()
    .map((iso) => ({
      iso,
      name: names?.of(iso) ?? iso,
      dial: `+${getCountryCallingCode(iso)}`,
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

let cached: PhoneCountry[] | null = null

/** Every country with a calling code, A–Z by name. Built once. */
export function phoneCountries(): PhoneCountry[] {
  return (cached ??= buildCountries())
}

export function findPhoneCountry(iso: string): PhoneCountry | undefined {
  return phoneCountries().find((c) => c.iso === iso)
}

/** `https://flagcdn.com/...` — image flags, because emoji flags do not render on Windows. */
export function flagUrl(iso: string, width: 20 | 40 = 40): string {
  return `https://flagcdn.com/w${width}/${iso.toLowerCase()}.png`
}

/**
 * Drop everything a phone number cannot contain as it is typed. Letters and
 * symbols never reach the field; spaces, dashes, dots and brackets are kept
 * because people type them. (A leading "+" is not kept — the country picker
 * owns the calling code.)
 */
export function sanitizePhoneInput(raw: string): string {
  return raw.replace(/[^\d\s().-]/g, '')
}

/** The E.164 form of a value, or null when it is not a valid number. */
export function phoneToE164(value: PhoneValue): string | null {
  const national = value.national.trim()
  if (!national) return null
  const parsed = parsePhoneNumberFromString(national, value.country)
  return parsed && parsed.isValid() ? parsed.number : null
}

/**
 * The message to show under a phone field, or undefined when it is fine.
 * An empty optional field is fine; an empty required one is not.
 */
export function phoneError(value: PhoneValue, required = false): string | undefined {
  if (!value.national.trim()) return required ? 'Enter your phone number' : undefined
  return phoneToE164(value) ? undefined : 'Enter a valid phone number'
}

/** Split a stored number back into country + digits for editing. */
export function phoneFromStored(stored: string | null | undefined): PhoneValue {
  const parsed = stored ? parsePhoneNumberFromString(stored) : undefined
  if (parsed?.country) {
    return { country: parsed.country, national: parsed.formatNational() }
  }
  // Unparseable legacy text is shown as-is so it can be seen and corrected.
  return { country: DEFAULT_PHONE_COUNTRY, national: stored ? sanitizePhoneInput(stored) : '' }
}
