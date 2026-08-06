"""
HTML email templates (jinja2).

A single branded base layout wraps each email's body. Templates are kept inline
(DictLoader) so the service has no filesystem dependency; add new emails by
adding a template string and a render helper.
"""
from jinja2 import Environment, DictLoader, select_autoescape

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(15,23,42,0.08);">
        <tr><td style="background:linear-gradient(135deg,#1168d4 0%,#1a85ff 100%);padding:22px 28px;">
          <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.01em;">{{ brand }}</span>
        </td></tr>
        <tr><td style="padding:32px 28px 8px;">
          {{ body }}
        </td></tr>
        <tr><td style="padding:24px 28px 32px;">
          <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 16px;">
          <p style="color:#94a3b8;font-size:12px;line-height:1.5;margin:0;">
            {{ footer }}
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

INVITATION_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">You're invited to join {{ organization_name }}</h1>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 20px;">
  {{ inviter_line }} has invited you to join <strong>{{ organization_name }}</strong> on {{ brand }}
  as a <strong>{{ role }}</strong>.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr>
    <td style="padding-right:10px;">
      <a href="{{ accept_url }}" style="display:inline-block;background:#1168d4;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 26px;border-radius:9px;">
        Accept invitation
      </a>
    </td>
    <td>
      <a href="{{ reject_url }}" style="display:inline-block;background:#ffffff;color:#475569;text-decoration:none;font-size:15px;font-weight:600;padding:12px 24px;border-radius:9px;border:1px solid #cbd5e1;">
        Decline
      </a>
    </td>
  </tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.6;margin:0;">
  This invitation expires on {{ expires_human }}. If the buttons don't work, copy and paste this link into your browser:<br>
  <a href="{{ accept_url }}" style="color:#1168d4;word-break:break-all;">{{ accept_url }}</a>
</p>
"""

VERIFICATION_CODE_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">{{ heading }}</h1>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 24px;">
  {{ intro }}
</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr>
    <td align="center" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:22px 16px;">
      <p style="color:#64748b;font-size:12px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 10px;">
        {{ code_label }}
      </p>
      <p style="color:#0f172a;font-size:34px;font-weight:700;letter-spacing:0.32em;margin:0;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;">
        {{ code }}
      </p>
    </td>
  </tr>
</table>
<p style="color:#334155;font-size:14px;line-height:1.6;margin:0 0 8px;">
  This code expires in <strong>{{ expires_minutes }} minutes</strong> and can only be used once.
</p>
<p style="color:#64748b;font-size:13px;line-height:1.6;margin:0;">
  {{ disclaimer }}
</p>
"""

BILLING_NOTICE_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">{{ heading }}</h1>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 20px;">
  {{ intro }}
</p>
{% if bullets %}
<ul style="color:#334155;font-size:14px;line-height:1.7;margin:0 0 22px;padding-left:20px;">
  {% for bullet in bullets %}<li>{{ bullet }}</li>{% endfor %}
</ul>
{% endif %}
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr><td>
    <a href="{{ action_url }}" style="display:inline-block;background:#1168d4;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 26px;border-radius:9px;">
      {{ action_label }}
    </a>
  </td></tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.6;margin:0;">
  {{ closing }}
</p>
"""

_env = Environment(
    loader=DictLoader(
        {
            "base": BASE_LAYOUT,
            "invitation": INVITATION_BODY,
            "verification_code": VERIFICATION_CODE_BODY,
            "billing_notice": BILLING_NOTICE_BODY,
        }
    ),
    autoescape=select_autoescape(["html", "xml"]),
)


def _wrap(body_html: str, footer: str, brand: str) -> str:
    return _env.get_template("base").render(body=body_html, footer=footer, brand=brand)


def render_verification_code_email(
    *,
    brand: str,
    code: str,
    expires_minutes: int,
    purpose: str,
    recipient_name: str | None = None,
) -> tuple[str, str, str]:
    """
    Return (html, text, subject) for a one-time code email.

    `purpose` is "signup" or "password_reset"; it only changes the wording, so
    the two emails stay visually identical and unmistakably from the same
    product.
    """
    def opening(sentence: str) -> str:
        """Prefix a greeting when we know the name, keeping the sentence readable."""
        if recipient_name:
            return f"Hi {recipient_name}, {sentence[0].lower()}{sentence[1:]}"
        return sentence

    if purpose == "password_reset":
        subject = f"Your {brand} password reset code"
        heading = "Reset your password"
        intro = opening(
            f"Use the code below to set a new password for your {brand} account."
        )
        code_label = "Password reset code"
        disclaimer = (
            "If you didn't ask to reset your password, you can ignore this "
            "email — your password stays as it is."
        )
    else:
        subject = f"Your {brand} verification code"
        heading = "Verify your email address"
        intro = opening(
            f"Enter the code below to confirm this email address and finish "
            f"creating your {brand} account."
        )
        code_label = "Verification code"
        disclaimer = (
            "If you didn't try to create an account, you can safely ignore "
            "this email."
        )

    body = _env.get_template("verification_code").render(
        heading=heading,
        intro=intro,
        code_label=code_label,
        code=code,
        expires_minutes=expires_minutes,
    )
    html = _wrap(
        body,
        footer=f"This is an automated message from {brand}. Never share this code with anyone — "
        f"{brand} will never ask you for it.",
        brand=brand,
    )
    text = (
        f"{heading}\n\n"
        f"{intro}\n\n"
        f"{code_label}: {code}\n\n"
        f"This code expires in {expires_minutes} minutes and can only be used once.\n\n"
        f"{disclaimer}\n"
        f"Never share this code with anyone — {brand} will never ask you for it."
    )
    return html, text, subject


def render_billing_notice_email(
    *,
    brand: str,
    heading: str,
    intro: str,
    action_url: str,
    action_label: str,
    bullets: list[str] | None = None,
    closing: str = "",
) -> tuple[str, str]:
    """Return (html, text) for a trial or subscription lifecycle notice.

    One template for the whole lifecycle — trial reminders, expiry, grace,
    payment failure — so the sequence reads as one conversation rather than
    five differently-designed emails.
    """
    bullets = bullets or []
    body = _env.get_template("billing_notice").render(
        heading=heading,
        intro=intro,
        bullets=bullets,
        action_url=action_url,
        action_label=action_label,
        closing=closing,
    )
    html = _wrap(
        body,
        footer=f"This is an automated message about your {brand} subscription.",
        brand=brand,
    )
    bullet_text = "".join(f"  - {bullet}\n" for bullet in bullets)
    text = (
        f"{heading}\n\n{intro}\n\n"
        f"{bullet_text}"
        f"\n{action_label}: {action_url}\n\n{closing}\n"
    )
    return html, text


def render_invitation_email(
    *,
    brand: str,
    organization_name: str,
    inviter_name: str | None,
    role: str,
    accept_url: str,
    reject_url: str,
    expires_human: str,
) -> tuple[str, str]:
    """Return (html, text) for a team invitation email."""
    inviter_line = f"{inviter_name}" if inviter_name else "Someone"
    body = _env.get_template("invitation").render(
        brand=brand,
        organization_name=organization_name,
        inviter_line=inviter_line,
        role=role,
        accept_url=accept_url,
        reject_url=reject_url,
        expires_human=expires_human,
    )
    html = _wrap(
        body,
        footer=f"You received this because {inviter_line} invited you to {organization_name} on {brand}. "
        f"If you weren't expecting this, you can safely ignore it.",
        brand=brand,
    )
    text = (
        f"{inviter_line} invited you to join {organization_name} on {brand} as a {role}.\n\n"
        f"Accept: {accept_url}\nDecline: {reject_url}\n\n"
        f"This invitation expires on {expires_human}."
    )
    return html, text
