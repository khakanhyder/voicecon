# Social Login (Google & Apple) — Setup Guide

This app supports **Sign in / Sign up with Google** and **Sign in with Apple**.
Both are implemented end-to-end (frontend + backend). They stay **disabled until
you add the credentials below** — until then the buttons show a friendly
"coming soon" toast and the backend returns a clear "not configured" error.

---

## How it works (architecture)

| Provider | Frontend flow | Backend verification |
|----------|---------------|----------------------|
| **Google** | Authorization-code popup via `@react-oauth/google` (`flow: 'auth-code'`, `redirect_uri='postmessage'`) | `/api/v1/auth/google` exchanges the code with Google using the client secret, then cryptographically verifies the returned **ID token** (signature + audience + issuer) via `google-auth` |
| **Apple** | Sign in with Apple JS popup (`AppleID.auth.signIn`) | `/api/v1/auth/apple` verifies the **ID token** against Apple's JWKS (signature + audience + issuer) |

On success the backend **finds-or-creates** the user:
1. Match by provider subject id (`google_id` / `apple_id`) → returning user.
2. Else, if the email is **verified**, link the provider to the existing account with that email (password stays intact — you can then use either method).
3. Else create a new user + a personal organization (owner membership), exactly like email signup.

The backend then issues the **same JWT access + refresh tokens** as password login, so sessions, refresh, `/auth/logout`, route guards and the rest of the app work identically. New users are routed to `/onboarding/company`; returning users go to `/dashboard`.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required for | Example / notes |
|----------|--------------|-----------------|
| `FRONTEND_URL` | both | `http://localhost:3002` (dev) / your prod URL |
| `GOOGLE_CLIENT_ID` | Google | `1234-abc.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google | `GOCSPX-...` |
| `APPLE_CLIENT_ID` | Apple | Your **Services ID**, e.g. `com.voicecon.web` |
| `APPLE_TEAM_ID` | Apple (code exchange only) | 10-char Team ID — *not needed for sign-in verification* |
| `APPLE_KEY_ID` | Apple (code exchange only) | Key ID of your `.p8` — *not needed for sign-in verification* |
| `APPLE_PRIVATE_KEY` | Apple (code exchange only) | Contents of the `.p8` — *not needed for sign-in verification* |

> Sign-in only needs `APPLE_CLIENT_ID`. The Team/Key/Private-key set is only for
> the authorization-code exchange (Apple refresh tokens), which this app does not
> require for authentication.

### Frontend (`frontend/.env.local`) — public, safe to expose

| Variable | Required for | Example / notes |
|----------|--------------|-----------------|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google | Same value as backend `GOOGLE_CLIENT_ID` |
| `NEXT_PUBLIC_APPLE_CLIENT_ID` | Apple | Same Services ID as backend `APPLE_CLIENT_ID` |
| `NEXT_PUBLIC_APPLE_REDIRECT_URI` | Apple | An **https** URL registered with Apple, e.g. `https://app.voicecon.com/login` |

After editing `.env` files, **restart** both servers (Next.js only reads
`NEXT_PUBLIC_*` at build/start time).

---

## Getting Google credentials (free, ~5 min)

1. Go to **[Google Cloud Console](https://console.cloud.google.com/)** → create/select a project.
2. **APIs & Services → OAuth consent screen**: choose **External**, fill app name, support email, and add your email as a **Test user** (while in "Testing" mode). Add scopes `email`, `profile`, `openid`.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - **Authorized JavaScript origins**: add every origin the app runs on:
     - `http://localhost:3002` (dev)
     - `https://your-frontend-domain.com` (prod)
   - **Authorized redirect URIs**: for the popup auth-code flow you can add the same origins (e.g. `http://localhost:3002`). The token exchange uses `postmessage`, so an exact redirect path is not required, but keep origins accurate.
4. Copy the **Client ID** and **Client secret**:
   - Backend `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
   - Frontend `.env.local`: `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
5. Restart both servers. `GET /api/v1/auth/providers` should now report `{"google": true}`.

> Publish the consent screen (Google → "Publish app") before real users outside
> your test list can sign in.

---

## Getting Apple credentials (requires paid Apple Developer Program — $99/yr)

> ⚠️ **Apple does not allow `http://localhost`.** Sign in with Apple only works on
> a registered **https domain**. Use a deployed domain or an https tunnel
> (e.g. ngrok/Cloudflare Tunnel) for testing.

1. **[Apple Developer](https://developer.apple.com/account/)** → Certificates, IDs & Profiles.
2. **Identifiers → App ID** (if you don't have one): create an App ID and enable **Sign in with Apple**.
3. **Identifiers → Services IDs → +**: create a Services ID (e.g. `com.voicecon.web`). This becomes `APPLE_CLIENT_ID` / `NEXT_PUBLIC_APPLE_CLIENT_ID`.
   - Configure it → enable **Sign in with Apple** → add your domain and the **Return URL** (must match `NEXT_PUBLIC_APPLE_REDIRECT_URI`, e.g. `https://app.voicecon.com/login`).
4. Set the env vars:
   - Backend `.env`: `APPLE_CLIENT_ID=com.voicecon.web`
   - Frontend `.env.local`: `NEXT_PUBLIC_APPLE_CLIENT_ID=com.voicecon.web`, `NEXT_PUBLIC_APPLE_REDIRECT_URI=https://app.voicecon.com/login`
5. *(Optional, only if you later add code exchange)* **Keys → +**: create a key with Sign in with Apple, download the `.p8` (once!). Fill `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`.
6. Restart servers. `GET /api/v1/auth/providers` should report `{"apple": true}`.

---

## Production checklist

- [ ] Backend `SECRET_KEY` is a long random value (JWTs are signed with it).
- [ ] `BACKEND_CORS_ORIGINS` includes your prod frontend origin.
- [ ] Google: prod origin added to **Authorized JavaScript origins**; consent screen **published**.
- [ ] Apple: prod domain + Return URL registered on the Services ID; `NEXT_PUBLIC_APPLE_REDIRECT_URI` matches exactly.
- [ ] Frontend served over **https** (required by Google GIS and Apple).
- [ ] `NEXT_PUBLIC_*` values set in the frontend host's build env (Render/Vercel/Railway) — they bake in at build time.
- [ ] Backend secrets (`GOOGLE_CLIENT_SECRET`, Apple keys) set as host secrets, never committed.

---

## Endpoints added

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/google` | `{ code }` → tokens + user |
| `POST` | `/api/v1/auth/apple` | `{ id_token, full_name?, nonce? }` → tokens + user |
| `GET`  | `/api/v1/auth/providers` | `{ google: bool, apple: bool }` — which are configured |

## Security notes

- ID tokens are verified **cryptographically** (signature, `aud`, `iss`, `exp`), not merely decoded.
- Accounts are linked only by a provider-**verified** email, preventing account takeover via an unverified address.
- Social-only accounts have a **null password**; attempting password login returns a clear "use Google/Apple" message instead of erroring.
- The frontend only ever holds public client IDs; the Google client secret and Apple private key live solely on the backend.
