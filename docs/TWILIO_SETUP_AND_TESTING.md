# Twilio Setup & Testing Guide

How to configure Twilio credentials, deploy so Twilio can reach the app, and test the
complete voice flow — plus what you can test in the browser right now.

---

## 0. Status after the Blocker 1 fix

**Blocker 1 (config crash) — FIXED.** The webhook/provisioning code read three settings
(`API_BASE_URL`, `WEBSOCKET_URL`, `SERVER_HOST`) that weren't declared, so provisioning a
number and receiving a call would have crashed with `AttributeError`. Those are now declared
in `config.py`. Verified: the settings resolve cleanly, and phone-number search now returns a
graceful "Twilio credentials not configured" instead of a crash.

So the Twilio integration is now genuinely **"credentials + public URL away"** from working.

---

## 1. Does a free server resolve Blocker 2? — Yes, with caveats

**Blocker 2** was: Twilio calls your webhooks from the internet, so it can't reach
`localhost`. Deploying to any host with a **public HTTPS URL resolves this** — Render,
Railway, Fly.io, etc. (Your git history shows Railway was already being set up, so that path
is a good fit.)

Two things the free host MUST support, or calls won't work:

1. **WebSockets (WSS).** Twilio Media Streams uses a WebSocket for the live audio. Render,
   Railway, and Fly.io support WS. Some free tiers (e.g. Vercel serverless) do **not** — the
   backend needs to run as a persistent server, not serverless functions.
2. **Always-on / no cold sleep during a call.** Free tiers often spin down after inactivity
   (Render free sleeps after ~15 min). A call to a sleeping server times out before it wakes.
   For reliable calls, use a tier that stays warm, or ping the health endpoint to keep it up.
   For a one-off test right after deploying (while it's warm), free is fine.

After deploying you set `API_BASE_URL` and `WEBSOCKET_URL` to your public URL (§3), and
Blocker 2 is fully resolved.

---

## 2. Where to put the Twilio credentials

The client will give you three things: **Account SID**, **Auth Token**, and (optionally) a
**Twilio phone number**. They go in the backend environment.

**Local dev:** `backend/.env`
**Deployed (Render/Railway/etc.):** the service's **Environment Variables** panel — do NOT
commit them to `.env` in git.

Full set of variables the voice feature needs:

```bash
# --- Twilio credentials (from the client / Twilio console) ---
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX          # optional default sender for SMS/outbound

# --- Public URLs so Twilio can reach this backend (Blocker 2) ---
# Use your DEPLOYED backend URL. Never localhost.
API_BASE_URL=https://your-backend.onrender.com      # https:// for webhooks
WEBSOCKET_URL=wss://your-backend.onrender.com        # wss:// for media streams
TWILIO_PUBLIC_BASE_URL=https://your-backend.onrender.com  # used by signature validation

# --- Voice providers (already working / paid) ---
OPENAI_API_KEY=sk-...            # or OpenRouter key + OPENAI_BASE_URL for testing
DEEPGRAM_API_KEY=...             # speech-to-text (working)
ELEVENLABS_API_KEY=...           # speech-out (your paid plan)

# --- Webhook security (recommended on) ---
TWILIO_VALIDATE_WEBHOOKS=true

# --- Persistence for encrypted credentials ---
ENCRYPTION_SALT=<stable 16-byte hex>   # already set; don't change it
```

Also set, for the frontend, so the browser talks to the deployed backend:
- Frontend env: `NEXT_PUBLIC_API_URL=https://your-backend.onrender.com`
- Backend `BACKEND_CORS_ORIGINS` must include your deployed frontend URL.

**Important:** `API_BASE_URL` must be an `https://` URL and `WEBSOCKET_URL` the matching
`wss://` — same host, different scheme. If you only set one, set `API_BASE_URL`; the code
falls back to the request Host header for the socket, but setting both is safest.

---

## 3. Step-by-step: test the complete flow after deployment

**Prerequisites:** app deployed, all env vars from §2 set, service restarted.

1. **Health check.** Open `https://your-backend.onrender.com/health` → expect `200`. Confirm
   the frontend loads and you can log in.

2. **ElevenLabs voice.** In the dashboard, open your agent → confirm it has a voice you own
   (paid plan) and a valid model, then use the **Live Test Call** (browser) → you should hear
   the agent speak. This proves TTS works before you spend a call on it.

3. **Provision a number.** Phone Numbers → **Search & Purchase** → search an area code →
   **Purchase**. It should appear under **My Numbers**. Assign it to your agent.

4. **Verify the webhook.** In the **Twilio console** → Phone Numbers → your number → confirm
   the Voice webhook points at `https://your-backend.onrender.com/api/v1/telephony/twilio/voice/<agent_id>`.
   (Provisioning sets this automatically from `API_BASE_URL`.)

5. **Call it.** From a real phone, dial the number. Expected:
   - You hear the agent's greeting (first message).
   - You speak; the agent understands and replies **in voice**.

6. **Verify the record.** Dashboard → **Calls** → the call appears with status, duration,
   **transcript**, and (if recording is on) a playable **recording**.

7. **Test a tool on the call.** Ask "What's the price of Bitcoin?" or a knowledge-base
   question → the agent should answer with live/retrieved data (same tools that work in the
   browser now work on the phone).

8. **Test telephony actions.** If the agent has transfer/hang-up/SMS tools, ask it to transfer
   you or text you → verify Twilio performs it.

### Pass criteria
Two-way spoken conversation on a real phone, a Call record with transcript, and tools firing.

### If it fails — quick triage
| Symptom | Likely cause |
|---|---|
| Number rings, then error/dead air | Webhook URL wrong or backend asleep (free-tier cold start) |
| Greeting plays, silence after you speak | Deepgram key, or STT not reaching the socket (check WSS support) |
| You're understood but agent has no voice | ElevenLabs key/plan/voice — check the agent's voice is one you own |
| Immediate hang-up / 403 in logs | Signature validation rejecting — verify `TWILIO_PUBLIC_BASE_URL` matches the real URL |
| "Twilio credentials not configured" | SID/token not set in the deployed environment |

---

## 4. What you can test in the browser RIGHT NOW

You don't need a public URL to test the **Twilio configuration** itself — only credentials.
Two separate things are browser-testable today:

### 4a. The Twilio account integration (Phone Numbers page)

This uses Twilio's REST API directly (no webhooks, no public URL needed):

1. Put `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in `backend/.env`, restart the backend.
2. Phone Numbers → **Search & Purchase** → enter an area code → **Search**.
   - **Working:** a list of real available numbers appears (this is a live Twilio API call).
   - **Not working:** "Twilio credentials not configured" = keys missing/wrong.
3. Optionally **Purchase** one (real, billable) → it appears under **My Numbers**; you can
   assign it to an agent or release it.

This confirms your Twilio credentials and the account integration work. What it does **not**
test is an actual call — that needs a phone and the public URL (§3).

> Note: purchasing while running on localhost will set the number's webhook to a localhost
> URL that Twilio can't reach. That's fine for testing the *purchase* flow; you'll re-point
> the webhook (or re-provision) after deploying, when `API_BASE_URL` is public.

### 4b. The voice pipeline (Live Test Call) — no Twilio at all

The agent's **Live Test Call** (mic → Deepgram → LLM → ElevenLabs) runs entirely in the
browser and tests everything *except* the Twilio transport. Use it to confirm your agent's
prompt, voice, and tools work before making a real call. With your paid ElevenLabs plan, you
should now hear the agent speak here.

---

## 5. Summary

| Item | State |
|---|---|
| Blocker 1 (config crash) | ✅ Fixed |
| Blocker 2 (public URL) | Resolved by deploying + setting `API_BASE_URL`/`WEBSOCKET_URL` |
| ElevenLabs (voice out) | ✅ You have a paid plan — set an owned voice on the agent |
| Twilio credentials | Add to backend env (§2); test via Phone Numbers page (§4a) |
| Real phone call | Works after deploy + creds + public URL + owned voice (§3) |

**Right now, before deployment:** add the Twilio SID/token locally and test Search & Purchase
in the browser (§4a), and use Live Test Call to confirm voice (§4b). **After deployment:**
set the public URLs and run the §3 checklist for a real call.
