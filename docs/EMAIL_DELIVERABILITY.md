# Email deliverability

How Voicecon's transactional email (verification codes, password resets,
team invitations, "member joined" notices, billing notices) is sent, and what
has to be true outside the codebase for it to land in the inbox.

Inbox placement is decided by the recipient's provider and can never be
guaranteed. What we control is authentication, sender reputation and message
hygiene — this document covers all three.

## What the app does (code)

`backend/app/services/email/` builds every message the same way:

| Item | Value | Why |
|---|---|---|
| From | `EMAIL_FROM_NAME <EMAIL_FROM>` (default `Voicecon <noreply@voicecon.ai>`) | One consistent sender identity |
| Envelope sender (MAIL FROM) | same as `EMAIL_FROM` | SPF is checked on the same domain the recipient sees (DMARC alignment) |
| Reply-To | `EMAIL_REPLY_TO` (default `support@voicecon.ai`) | A no-reply sender with nowhere to reply reads as bulk mail |
| Message-ID | `<…@voicecon.ai>` (the From domain) | Previously used `SERVER_HOST`, a mismatch filters penalise |
| Date | UTC | |
| EHLO name | `SMTP_HELO_NAME`, else the From domain | Not the container's random hostname |
| Auto-Submitted | `auto-generated` | RFC 3834: stops auto-responders replying to noreply |
| X-Auto-Response-Suppress | `OOF, AutoReply` | Stops Outlook/Exchange out-of-office replies |
| Body | `multipart/alternative`, text/plain + HTML | HTML-only mail scores worse; text is generated if a caller omits it |
| Escaping | Jinja autoescape **on** | User-supplied names can't inject links into our email |

Content rules the templates follow: a clear subject that says what the email
is, one call-to-action button plus the same link as plain text, no images, no
URL shorteners, no ALL-CAPS or "free/urgent" wording, and a footer saying why
the recipient got the email.

Settings live in `.env` or the admin console (Admin → API Keys → Email).

## What has to be configured outside the app

Checked on 2026-09-27 against live DNS:

| Check | Current state | Needed |
|---|---|---|
| SPF (`voicecon.ai` TXT) | `v=spf1 ip4:154.12.252.102 +a +mx ~all` | OK to keep; tighten to `-all` once DKIM passes. Drop `+a` (the apex is proxied by Cloudflare, so it authorises Cloudflare's IPs, not ours). |
| DKIM | **No record found** (checked `default`, `mail`, `dkim`, `google`, `s1`, `x`, `selector1/2`, `k1` …) | **Enable DKIM signing on the sending server and publish its public key** as `<selector>._domainkey.voicecon.ai`. This is the single biggest fix. |
| DMARC (`_dmarc.voicecon.ai`) | `v=DMARC1; p=none; rua=…cloudflare…` | Keep `p=none` while monitoring the Cloudflare DMARC reports; once SPF + DKIM both pass for all legitimate mail, move to `p=quarantine`, then `p=reject`. |
| Reverse DNS (PTR) of the sending IP | `154.12.252.102` → `vmi1844490.contaboserver.net`; the server greets as `server.vconekthost.com` | Set the PTR (in the Contabo panel) to `mail.voicecon.ai`, and make the server's hostname/EHLO `mail.voicecon.ai` so forward and reverse DNS match. |
| Sending IP | Self-hosted Exim on a Contabo VPS (`mail.voicecon.ai`) | VPS ranges often carry poor reputation. Strongly consider a transactional provider (Postmark, Amazon SES, Resend, SendGrid) with its DKIM + custom return-path on a subdomain such as `mail.voicecon.ai` or `notify.voicecon.ai`. The app already supports SMTP and SendGrid. |
| `support@voicecon.ai` | Must exist and be monitored | It is the Reply-To. |
| Links in email | `FRONTEND_URL` must be the public app URL (`https://app.voicecon.ai`) | Emails sent from a local dev backend contain `http://localhost:3000` links, which spam filters flag. Don't send real invites from a local stack. |

### Verifying

1. Send an invitation to the address shown on <https://www.mail-tester.com>
   and aim for 9/10 or better; it reports SPF, DKIM, DMARC, rDNS and content.
2. In Gmail, open a received email → ⋮ → *Show original*: `SPF: PASS`,
   `DKIM: PASS` and `DMARC: PASS` must all be present, with DKIM `d=voicecon.ai`.
3. Register the domain in Google Postmaster Tools to watch reputation.

Also avoid sending test mail to non-existent addresses through the production
server: the resulting bounces count against sender reputation.
