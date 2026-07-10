/**
 * Centralised SVG icon components for the onboarding / auth flow.
 *
 * Keep all reusable SVG marks here and import them where needed, e.g.:
 *   import { GoogleIcon, BrandPanelIcons } from '@/lib/icons'
 *
 * NOTE: <RobotIllustration> renders /brand/robot.png. Drop the exported PNG
 * from the Figma file at `frontend/public/brand/robot.png` and it will appear
 * with no code changes. (The asset is a raster image, so it lives in /public
 * rather than as an inline vector.)
 */
import Image from 'next/image'
import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

/* ────────────────────────────── Brand ────────────────────────────── */

/** Voicecon wordmark mic logo (green). */
export function VoiceconLogo({ className = 'h-6 w-6', ...props }: IconProps) {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M22.3067 10.64C21.8517 10.64 21.49 11.0017 21.49 11.4567V13.3C21.49 17.43 18.13 20.79 14 20.79C9.87004 20.79 6.51004 17.43 6.51004 13.3V11.445C6.51004 10.99 6.14838 10.6283 5.69338 10.6283C5.23838 10.6283 4.87671 10.99 4.87671 11.445V13.2883C4.87671 18.0367 8.52838 21.945 13.1834 22.365V24.85C13.1834 25.305 13.545 25.6667 14 25.6667C14.455 25.6667 14.8167 25.305 14.8167 24.85V22.365C19.46 21.9567 23.1234 18.0367 23.1234 13.2883V11.445C23.1117 11.0017 22.75 10.64 22.3067 10.64Z"
        fill="#0F6A59"
      />
      <path
        d="M14.0001 2.33333C11.1534 2.33333 8.84338 4.64333 8.84338 7.49V13.4633C8.84338 16.31 11.1534 18.62 14.0001 18.62C16.8467 18.62 19.1567 16.31 19.1567 13.4633V7.49C19.1567 4.64333 16.8467 2.33333 14.0001 2.33333ZM15.5284 10.4417C15.4467 10.745 15.1784 10.9433 14.875 10.9433C14.8167 10.9433 14.7584 10.9317 14.7001 10.92C14.2451 10.7917 13.7667 10.7917 13.3117 10.92C12.9384 11.025 12.5767 10.8033 12.4834 10.4417C12.3784 10.08 12.6 9.70666 12.9617 9.61333C13.65 9.42666 14.3734 9.42666 15.0617 9.61333C15.4117 9.70666 15.6217 10.08 15.5284 10.4417ZM16.1467 8.17833C16.0417 8.45833 15.785 8.62166 15.505 8.62166C15.4234 8.62166 15.3534 8.60999 15.2717 8.58666C14.455 8.28333 13.545 8.28333 12.7284 8.58666C12.3784 8.71499 11.9817 8.52833 11.8534 8.17833C11.725 7.82833 11.9117 7.43166 12.2617 7.31499C13.3817 6.90666 14.6184 6.90666 15.7384 7.31499C16.0884 7.44333 16.275 7.82833 16.1467 8.17833Z"
        fill="#0F6A59"
      />
    </svg>
  )
}

/** Plan icon — "Sales Chatbot" (bordered square + sparkle, brand green). */
export function SalesChatbotIcon({ className = 'h-8 w-8', ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 25 25"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <g clipPath="url(#clip0_380_1143)">
        <path
          d="M21.3665 0.0449219H3.63386C1.65175 0.0449219 0.0449219 1.65175 0.0449219 3.63386V21.3665C0.0449219 23.3486 1.65175 24.9554 3.63386 24.9554H21.3665C23.3486 24.9554 24.9554 23.3486 24.9554 21.3665V3.63386C24.9554 1.65175 23.3486 0.0449219 21.3665 0.0449219Z"
          stroke="#0F6A59"
          strokeMiterlimit="10"
        />
        <path
          d="M13.2364 19.4416C13.7428 18.0341 14.5597 16.7098 15.6863 15.577L15.7068 15.5565C16.8351 14.4281 18.1531 13.6094 19.5553 13.0985C20.4286 12.7809 21.3341 12.5822 22.2458 12.5044C21.3368 12.4543 20.4339 12.2834 19.5633 11.9935C18.1021 11.5085 16.7331 10.6862 15.5735 9.52657C14.4148 8.36784 13.5916 6.99704 13.1066 5.53677C12.7952 4.60084 12.6225 3.62732 12.5876 2.64844L12.5501 2.68602C12.483 3.65774 12.2798 4.62231 11.9416 5.55019C11.4325 6.94604 10.6156 8.25957 9.49352 9.38519L9.48546 9.39325C8.36431 10.5144 7.05436 11.3313 5.6612 11.8422C4.72705 12.1849 3.75622 12.3898 2.77823 12.4579L2.7666 12.4695C3.7437 12.5044 4.71453 12.6771 5.64867 12.9867C7.11073 13.4725 8.48332 14.2948 9.64384 15.4562C10.8053 16.6177 11.6267 17.9885 12.1125 19.4514C12.423 20.3856 12.5957 21.3564 12.6306 22.3335L12.6369 22.3272C12.6986 21.3492 12.8981 20.3766 13.2346 19.4407L13.2364 19.4416Z"
          fill="#0F6A59"
        />
      </g>
      <defs>
        <clipPath id="clip0_380_1143">
          <rect width="25" height="25" fill="white" />
        </clipPath>
      </defs>
    </svg>
  )
}

/** Plan icon — "Voice AI" (bordered square + flower, white for the green card). */
export function VoiceAiIcon({ className = 'h-8 w-8', ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 25 25"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <g clipPath="url(#clip0_380_1177)">
        <path
          d="M21.3665 0.0449219H3.63386C1.65175 0.0449219 0.0449219 1.65175 0.0449219 3.63386V21.3665C0.0449219 23.3486 1.65175 24.9554 3.63386 24.9554H21.3665C23.3486 24.9554 24.9554 23.3486 24.9554 21.3665V3.63386C24.9554 1.65175 23.3486 0.0449219 21.3665 0.0449219Z"
          stroke="white"
          strokeMiterlimit="10"
        />
        <path
          d="M21.5373 7.60838V12.6469C16.8586 12.6012 13.0459 8.93533 12.7686 4.31472V3.46289H17.552C17.5511 3.48615 17.5511 3.50942 17.5511 3.53268C17.5511 5.75441 19.3273 7.56096 21.5373 7.60838Z"
          fill="white"
        />
        <path
          d="M12.0527 3.81991C12.0527 8.62663 8.23293 12.5395 3.46289 12.6907V7.64686C5.58082 7.50011 7.25315 5.73562 7.25315 3.58011C7.25315 3.54074 7.25226 3.50226 7.25137 3.46289H12.0447C12.05 3.581 12.0527 3.70001 12.0527 3.81991Z"
          fill="white"
        />
        <path
          d="M11.9919 21.5371H7.19231C6.9543 19.6285 5.39739 18.1298 3.46289 17.9821V13.417C7.96898 13.5727 11.6206 17.0883 11.9919 21.5371Z"
          fill="white"
        />
        <path
          d="M21.5375 13.4424V18.0022C19.5171 18.0541 17.8636 19.5752 17.6041 21.5374H12.8027C13.1946 17.0358 16.9473 13.4961 21.5375 13.4424Z"
          fill="white"
        />
      </g>
      <defs>
        <clipPath id="clip0_380_1177">
          <rect width="25" height="25" fill="white" />
        </clipPath>
      </defs>
    </svg>
  )
}

/* ────────────────────────────── Social ───────────────────────────── */

export function GoogleIcon({ className = 'h-5 w-5', ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...props}>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z"
      />
    </svg>
  )
}

export function AppleIcon({ className = 'h-5 w-5', ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" {...props}>
      <path d="M16.37 1.43c.09 1-.31 2-.95 2.72-.68.77-1.78 1.36-2.85 1.28-.11-.98.36-2 .96-2.66.68-.77 1.84-1.34 2.84-1.34ZM19.6 17.2c-.53 1.22-.78 1.76-1.46 2.84-.95 1.51-2.29 3.4-3.95 3.41-1.47.02-1.85-.96-3.85-.95-2 .01-2.42.97-3.9.94-1.66-.02-2.93-1.72-3.88-3.23-2.66-4.24-2.94-9.21-1.3-11.86C2.51 6.52 4.2 5.5 5.79 5.5c1.62 0 2.64 1.03 3.98 1.03 1.3 0 2.09-1.03 3.97-1.03 1.42 0 2.92.78 3.99 2.12-3.5 1.92-2.93 6.92.87 8.58-.31.96-.66 1.92-1 .99Z" />
    </svg>
  )
}

/* ──────────────────────── Robot illustration ─────────────────────── */

/**
 * Hero robot for the green brand panel. Renders /brand/robot.png as a CSS
 * background so a missing asset degrades gracefully (shows nothing rather
 * than a broken-image icon). Server-component safe — no event handlers.
 */
export function RobotIllustration({ className = '' }: { className?: string }) {
  return (
    <Image
      src="/brand/robot.png"
      alt="Voicecon AI assistant"
      width={180}
      height={187}
      priority
      className={className}
    />
  )
}

/**
 * The integration chips that orbit the robot. Each PNG already includes its
 * own coloured circular background, so they render as plain images.
 *
 * Coordinates are in the BrandPanel's 400×400 illustration coordinate system
 * (robot centred at 200,200). `cx`/`cy` = chip centre; `connector` = the
 * dashed right-angle path from the chip toward the robot.
 */
export const BRAND_STAGE = 400
export const BRAND_CHIP = 56

export const BrandPanelIcons = [
  {
    key: 'hubspot',
    src: '/brand/hubspot.png',
    alt: 'HubSpot',
    cx: 78,
    cy: 150,
    connector: 'M78 150 V196 H150',
  },
  {
    key: 'twilio',
    src: '/brand/twilio.png',
    alt: 'Twilio',
    cx: 322,
    cy: 122,
    connector: 'M322 122 H250 V190',
  },
  {
    key: 'zendesk',
    src: '/brand/zendex.png',
    alt: 'Zendesk',
    cx: 96,
    cy: 286,
    connector: 'M96 286 H160 V228',
  },
  {
    key: 'openai',
    src: '/brand/openai.png',
    alt: 'OpenAI',
    cx: 326,
    cy: 282,
    connector: 'M326 282 V228 H252',
  },
] as const
