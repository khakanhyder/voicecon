/**
 * Facts shared by the Privacy Policy and Terms of Service. Change dates here
 * whenever either document changes, so both pages stay in step.
 *
 * Company details are VConekt LLC's, as published on vconekt.com. Voicecon is
 * a product of VConekt LLC, so the LLC is the contracting party and the data
 * controller.
 */
export const LEGAL = {
  product: 'Voicecon',
  company: 'VConekt LLC',
  /** Where the company is registered — this drives the governing-law clause. */
  jurisdiction: 'State of Wyoming, United States',
  courts: 'the state and federal courts located in Sheridan County, Wyoming',
  registeredAddress: '30 N Gould St Ste 25084, Sheridan, WY 82801-6317, USA',
  officeAddress: 'Pakland Tower 2, Unit 308, New Blue Area, Islamabad, Pakistan',
  phone: '+1 210 444 2037',
  phoneHref: '+12104442037',
  website: 'https://voicecon.ai',
  appUrl: 'https://app.voicecon.ai',
  companyWebsite: 'https://vconekt.com',
  contactEmail: 'support@voicecon.ai',
  /** Privacy requests and data-subject rights. Legal notices and security
   *  reports go to contactEmail — those inboxes don't exist yet. */
  privacyEmail: 'privacy@voicecon.ai',
  effectiveDate: 'September 18, 2026',
  effectiveDateIso: '2026-09-18',
  lastUpdated: 'September 18, 2026',
  lastUpdatedIso: '2026-09-18',
} as const
