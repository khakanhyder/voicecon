"""
OAuth provider registry.

Holds the public OAuth endpoints (authorize/token URLs, default scopes) for each
OAuth2 connector, plus which environment variables carry that provider's client
credentials. The platform owner registers ONE OAuth app per provider and sets the
corresponding *_CLIENT_ID / *_CLIENT_SECRET env vars; every end user then connects
through that shared app (standard multi-tenant SaaS OAuth).

Endpoints and scopes here are public, provider-documented values. Client id/secret
are secrets and come only from the environment.
"""
import os
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from app.core.config import env_value


# slug -> provider OAuth config
OAUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "google-calendar": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
        # Needed for Google to return a refresh_token.
        "authorize_params": {"access_type": "offline", "prompt": "consent"},
    },
    "google-sheets": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
        "authorize_params": {"access_type": "offline", "prompt": "consent"},
    },
    "google-drive": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
        "authorize_params": {"access_type": "offline", "prompt": "consent"},
    },
    "hubspot": {
        "authorize_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        # Every scope the connector's actions need. "contacts" (the old broad
        # scope) is being sunset and HubSpot has already migrated app configs to
        # the granular ones, so asking for it now fails the authorize step.
        # "oauth" is what /account-info (the connection test) needs; deals.write
        # is what create_deal needs.
        "scopes": [
            "oauth",
            "crm.objects.contacts.read",
            "crm.objects.contacts.write",
            "crm.objects.deals.read",
            "crm.objects.deals.write",
        ],
        "client_id_env": "HUBSPOT_CLIENT_ID",
        "client_secret_env": "HUBSPOT_CLIENT_SECRET",
    },
    "salesforce": {
        "authorize_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "scopes": ["api", "refresh_token"],
        "client_id_env": "SALESFORCE_CLIENT_ID",
        "client_secret_env": "SALESFORCE_CLIENT_SECRET",
        # login.salesforce.com only works for an app any org can authorize. A
        # Local External Client App (Salesforce's app type since Connected App
        # creation was disabled) rejects it with OAUTH_AUTHORIZATION_BLOCKED
        # "cross-org OAuth flows are not supported"; it has to be authorized on
        # the My Domain host of the org that owns it. Sandboxes likewise need
        # test.salesforce.com. SALESFORCE_LOGIN_URL swaps the host for both
        # endpoints, e.g. https://example.my.salesforce.com.
        "host_env": "SALESFORCE_LOGIN_URL",
    },
    "slack": {
        "authorize_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        # users:read backs the connector's users.info / users.list actions.
        "scopes": ["chat:write", "channels:read", "users:read"],
        "client_id_env": "SLACK_CLIENT_ID",
        "client_secret_env": "SLACK_CLIENT_SECRET",
    },
    "notion": {
        "authorize_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scopes": [],
        "client_id_env": "NOTION_CLIENT_ID",
        "client_secret_env": "NOTION_CLIENT_SECRET",
        "authorize_params": {"owner": "user"},
        # Notion authenticates the token request with HTTP Basic (client_id:
        # client_secret) and requires a JSON body; credentials in a form body
        # get a 401.
        "token_style": "basic_json",
    },
    "clickup": {
        "authorize_url": "https://app.clickup.com/api",
        "token_url": "https://api.clickup.com/api/v2/oauth/token",
        # ClickUp has no scope parameter; access is granted per workspace the
        # user selects during authorization.
        "scopes": [],
        "client_id_env": "CLICKUP_CLIENT_ID",
        "client_secret_env": "CLICKUP_CLIENT_SECRET",
        # ClickUp's token endpoint accepts exactly client_id, client_secret and
        # code. Sending the usual grant_type/redirect_uri alongside them is
        # rejected with 401 Unauthorized.
        "token_style": "clickup",
    },
    "calendly": {
        "authorize_url": "https://auth.calendly.com/oauth/authorize",
        "token_url": "https://auth.calendly.com/oauth/token",
        "scopes": ["default"],
        "client_id_env": "CALENDLY_CLIENT_ID",
        "client_secret_env": "CALENDLY_CLIENT_SECRET",
    },
    "monday": {
        "authorize_url": "https://auth.monday.com/oauth2/authorize",
        "token_url": "https://auth.monday.com/oauth2/token",
        "scopes": ["boards:read", "boards:write"],
        # Send no scope param: monday then grants every scope configured on the
        # app. Other accounts authorize against the app's *live* version, while
        # the developer's own account sees the draft — so an explicit list that
        # names any scope the live version lacks fails with invalid_scope for
        # everyone except the app owner.
        "omit_scope": True,
        "client_id_env": "MONDAY_CLIENT_ID",
        "client_secret_env": "MONDAY_CLIENT_SECRET",
    },
}


def _apply_host_override(url: Optional[str], host: Optional[str]) -> Optional[str]:
    """Re-point ``url`` at ``host``, keeping the provider's documented path."""
    if not url or not host:
        return url
    base = host.strip().rstrip("/")
    if not base:
        return url
    if "://" not in base:
        base = f"https://{base}"
    return urljoin(base + "/", urlparse(url).path.lstrip("/"))


def get_oauth_provider(slug: str) -> Optional[Dict[str, Any]]:
    """Return the OAuth config for a connector slug, or None if unregistered."""
    return OAUTH_PROVIDERS.get(slug)


def resolve_client_credentials(
    slug: str,
    auth_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """
    Resolve client_id / client_secret for a connector.

    Priority: environment variable (platform-level OAuth app) first, then any
    value seeded in the connector's auth_config (override/legacy). Endpoints and
    scopes come from the registry, with auth_config allowed to override.

    Returns a dict with authorize_url, token_url, scopes, authorize_params,
    token_style, client_id, client_secret (any of which may be None if
    unconfigured).
    """
    auth_config = auth_config or {}
    provider = OAUTH_PROVIDERS.get(slug, {})

    # env_value, not os.getenv: pydantic loads .env into the Settings object but
    # never exports it to the process environment, so os.getenv returned None
    # for credentials that were present and correct in .env — and the user was
    # told to go and register an OAuth app they already had.
    client_id = None
    client_secret = None
    if provider.get("client_id_env"):
        client_id = env_value(provider["client_id_env"])
    if provider.get("client_secret_env"):
        client_secret = env_value(provider["client_secret_env"])

    # auth_config can override/supply (e.g. self-hosted or per-tenant apps)
    client_id = auth_config.get("client_id") or client_id
    client_secret = auth_config.get("client_secret") or client_secret

    # A provider may allow the login host to be swapped (Salesforce My Domain /
    # sandbox). The override is applied last, to whichever URL we ended up with:
    # the seeded connector row carries its own token_url, so overriding only the
    # registry default sent the authorize step to the My Domain host and the
    # token exchange back to login.salesforce.com — half-migrated and broken.
    host = env_value(provider["host_env"]) if provider.get("host_env") else None
    authorize_url = _apply_host_override(
        auth_config.get("authorize_url") or provider.get("authorize_url"), host
    )
    token_url = _apply_host_override(
        auth_config.get("token_url") or provider.get("token_url"), host
    )

    return {
        "authorize_url": authorize_url,
        "token_url": token_url,
        "scopes": auth_config.get("scopes") or provider.get("scopes", []),
        "omit_scope": bool(provider.get("omit_scope")),
        "authorize_params": provider.get("authorize_params", {}),
        "token_style": auth_config.get("token_style") or provider.get("token_style") or "form",
        "client_id": client_id,
        "client_secret": client_secret,
    }
