// Sign in with Apple (JS) helper.
//
// Loads Apple's official SDK on demand and runs the popup sign-in flow.
// Returns the identity token (verified server-side) plus the display name,
// which Apple only provides on the user's very first authorization.
//
// Note: Apple does not allow http/localhost return URLs — it requires an
// https domain registered in the Apple Developer portal. So this only works
// against a deployed/tunneled https origin, not `http://localhost`.

const APPLE_SDK_URL =
  'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js'

let sdkPromise: Promise<void> | null = null

function loadAppleSdk(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('No window'))
  if ((window as any).AppleID) return Promise.resolve()
  if (sdkPromise) return sdkPromise

  sdkPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = APPLE_SDK_URL
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      sdkPromise = null
      reject(new Error('Failed to load the Apple sign-in SDK'))
    }
    document.head.appendChild(script)
  })
  return sdkPromise
}

export function isAppleConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_APPLE_CLIENT_ID && process.env.NEXT_PUBLIC_APPLE_REDIRECT_URI,
  )
}

export interface AppleSignInResult {
  id_token: string
  full_name?: string
}

export async function signInWithApple(): Promise<AppleSignInResult> {
  const clientId = process.env.NEXT_PUBLIC_APPLE_CLIENT_ID
  const redirectURI = process.env.NEXT_PUBLIC_APPLE_REDIRECT_URI
  if (!clientId || !redirectURI) {
    throw new Error('Apple sign-in is not configured')
  }

  await loadAppleSdk()
  const AppleID = (window as any).AppleID
  AppleID.auth.init({
    clientId,
    scope: 'name email',
    redirectURI,
    usePopup: true,
  })

  const response = await AppleID.auth.signIn()
  const idToken: string | undefined = response?.authorization?.id_token
  if (!idToken) {
    throw new Error('Apple did not return an identity token')
  }

  let fullName: string | undefined
  const name = response?.user?.name
  if (name) {
    fullName = [name.firstName, name.lastName].filter(Boolean).join(' ') || undefined
  }

  return { id_token: idToken, full_name: fullName }
}
