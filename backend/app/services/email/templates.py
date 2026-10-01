"""
HTML email templates (jinja2).

A single branded base layout wraps each email's body. Templates are kept inline
(DictLoader) so the service has no filesystem dependency; add new emails by
adding a template string and a render helper.
"""
from jinja2 import Environment, DictLoader
from markupsafe import Markup

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(15,23,42,0.08);">
        <tr><td style="background:#0F6A59;padding:22px 28px;">
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
      <a href="{{ accept_url }}" style="display:inline-block;background:#0F6A59;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 26px;border-radius:9px;">
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
  <a href="{{ accept_url }}" style="color:#0F6A59;word-break:break-all;">{{ accept_url }}</a>
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

EMAIL_CHANGED_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">Your email address was changed</h1>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 16px;">
  {{ opening }} email address for your {{ brand }} account was changed to
  <strong>{{ new_email }}</strong>. This address ({{ old_email }}) can no longer be used to sign in.
</p>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 16px;">
  If you made this change, there is nothing more to do.
</p>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0;">
  <strong>If you did not make this change</strong>, someone else may have access to your account.
  Contact us straight away at <a href="mailto:{{ support_email }}" style="color:#0F6A59;">{{ support_email }}</a>.
</p>
"""

ACCOUNT_NOTICE_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">{{ heading }}</h1>
{% for paragraph in paragraphs %}
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 16px;">
  {{ paragraph }}
</p>
{% endfor %}
{% if support_line %}
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0;">
  {{ support_line }}
  <a href="mailto:{{ support_email }}" style="color:#0F6A59;">{{ support_email }}</a>.
</p>
{% endif %}
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
    <a href="{{ action_url }}" style="display:inline-block;background:#0F6A59;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 26px;border-radius:9px;">
      {{ action_label }}
    </a>
  </td></tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.6;margin:0;">
  {{ closing }}
</p>
"""

MEMBER_JOINED_BODY = """
<h1 style="color:#0f172a;font-size:22px;font-weight:700;margin:0 0 12px;">{{ member_name }} joined {{ organization_name }}</h1>
<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 20px;">
  {{ greeting }}<strong>{{ member_name }}</strong>{% if member_email != member_name %} ({{ member_email }}){% endif %}
  has accepted your invitation and joined <strong>{{ organization_name }}</strong> as a <strong>{{ role }}</strong>.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr><td>
    <a href="{{ team_url }}" style="display:inline-block;background:#0F6A59;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:12px 26px;border-radius:9px;">
      View your team
    </a>
  </td></tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.6;margin:0;">
  You can change their role or remove them from the workspace at any time on the Team page.
</p>
"""

_env = Environment(
    loader=DictLoader(
        {
            "base": BASE_LAYOUT,
            "invitation": INVITATION_BODY,
            "verification_code": VERIFICATION_CODE_BODY,
            "billing_notice": BILLING_NOTICE_BODY,
            "email_changed": EMAIL_CHANGED_BODY,
            "account_notice": ACCOUNT_NOTICE_BODY,
            "member_joined": MEMBER_JOINED_BODY,
        }
    ),
    # Always escape. select_autoescape(["html", "xml"]) decides by file
    # extension, and these inline templates have none, so it escaped nothing:
    # a workspace or user name containing HTML (a link, say) was sent verbatim
    # from our domain — a phishing vector and a spam-filter red flag.
    autoescape=True,
)


def _wrap(body_html: str, footer: str, brand: str) -> str:
    # body_html was rendered (and escaped) by one of the body templates above.
    return _env.get_template("base").render(body=Markup(body_html), footer=footer, brand=brand)


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

    `purpose` is "signup", "password_reset", "email_change" or
    "account_deactivation"; it only changes
    the wording, so the emails stay visually identical and unmistakably from the same
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
    elif purpose == "email_change":
        subject = f"Confirm your new {brand} email address"
        heading = "Confirm your new email address"
        intro = opening(
            f"Enter the code below to make this the email address for your "
            f"{brand} account."
        )
        code_label = "Confirmation code"
        disclaimer = (
            "If you didn't ask to change your email address, you can ignore "
            "this email — nothing on the account changes without this code."
        )
    elif purpose == "account_deactivation":
        subject = f"Confirm deactivating your {brand} account"
        heading = "Confirm it's you"
        intro = opening(
            f"Enter the code below to continue deactivating your {brand} account."
        )
        code_label = "Confirmation code"
        disclaimer = (
            "If you didn't ask to deactivate your account, you can ignore this "
            "email — nothing happens to the account without this code."
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


def render_email_changed_notice(
    *,
    brand: str,
    old_email: str,
    new_email: str,
    support_email: str,
    recipient_name: str | None = None,
) -> tuple[str, str, str]:
    """
    Return (html, text, subject) for the notice sent to the *previous* address
    after an email change, so the owner hears about a change they did not make.
    """
    subject = f"Your {brand} email address was changed"
    body = _env.get_template("email_changed").render(
        opening=f"Hi {recipient_name}, the" if recipient_name else "The",
        brand=brand,
        old_email=old_email,
        new_email=new_email,
        support_email=support_email,
    )
    html = _wrap(
        body,
        footer=f"This is an automated security message from {brand}.",
        brand=brand,
    )
    opening = f"Hi {recipient_name}, the" if recipient_name else "The"
    text = (
        f"Your email address was changed\n\n"
        f"{opening} email address for your {brand} account was changed to {new_email}. "
        f"This address ({old_email}) can no longer be used to sign in.\n\n"
        f"If you made this change, there is nothing more to do.\n\n"
        f"If you did not make this change, someone else may have access to your "
        f"account. Contact us straight away at {support_email}.\n"
    )
    return html, text, subject


def render_account_notice_email(
    *,
    brand: str,
    heading: str,
    paragraphs: list[str],
    support_email: str,
    support_line: str = "",
) -> tuple[str, str]:
    """Return (html, text) for an account lifecycle notice: deactivated,
    reactivated or permanently deleted.

    ``support_line`` is the sentence that ends with the support address, for
    example "To reactivate your account, contact us at".
    """
    body = _env.get_template("account_notice").render(
        heading=heading,
        paragraphs=paragraphs,
        support_line=support_line,
        support_email=support_email,
    )
    html = _wrap(body, footer=f"This is an automated message about your {brand} account.", brand=brand)
    text = f"{heading}\n\n" + "\n\n".join(paragraphs) + "\n"
    if support_line:
        text += f"\n{support_line} {support_email}.\n"
    return html, text


def render_billing_notice_email(
    *,
    brand: str,
    heading: str,
    intro: str,
    action_url: str,
    action_label: str,
    bullets: list[str] | None = None,
    closing: str = "",
    footer: str | None = None,
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
        footer=footer or f"This is an automated message about your {brand} subscription.",
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


def render_member_joined_email(
    *,
    brand: str,
    member_name: str,
    member_email: str,
    organization_name: str,
    role: str,
    team_url: str,
    recipient_name: str | None = None,
) -> tuple[str, str, str]:
    """Return (html, text, subject) telling the owner an invitee has joined."""
    greeting = f"Hi {recipient_name}, " if recipient_name else ""
    subject = f"{member_name} joined {organization_name} on {brand}"
    body = _env.get_template("member_joined").render(
        greeting=greeting,
        member_name=member_name,
        member_email=member_email,
        organization_name=organization_name,
        role=role,
        team_url=team_url,
    )
    html = _wrap(
        body,
        footer=f"You received this because you manage the {organization_name} workspace on {brand}.",
        brand=brand,
    )
    who = member_name if member_email == member_name else f"{member_name} ({member_email})"
    text = (
        f"{greeting}{who} has accepted your invitation and joined {organization_name} as a {role}.\n\n"
        f"View your team: {team_url}\n\n"
        f"You received this because you manage the {organization_name} workspace on {brand}."
    )
    return html, text, subject
