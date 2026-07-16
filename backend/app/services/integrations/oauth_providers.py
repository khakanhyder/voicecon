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
        "scopes": ["crm.objects.contacts.read", "crm.objects.contacts.write", "oauth"],
        "client_id_env": "HUBSPOT_CLIENT_ID",
        "client_secret_env": "HUBSPOT_CLIENT_SECRET",
    },
    "salesforce": {
        "authorize_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "scopes": ["api", "refresh_token"],
        "client_id_env": "SALESFORCE_CLIENT_ID",
        "client_secret_env": "SALESFORCE_CLIENT_SECRET",
    },
    "slack": {
        "authorize_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["chat:write", "channels:read"],
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
    },
    "clickup": {
        "authorize_url": "https://app.clickup.com/api",
        "token_url": "https://api.clickup.com/api/v2/oauth/token",
        # ClickUp has no scope parameter; access is granted per workspace the
        # user selects during authorization.
        "scopes": [],
        "client_id_env": "CLICKUP_CLIENT_ID",
        "client_secret_env": "CLICKUP_CLIENT_SECRET",
    },
    "calendly": {
        "authorize_url": "https://auth.calendly.com/oauth/authorize",
        "token_url": "https://auth.calendly.com/oauth/token",
        "scopes": ["default"],
        "client_id_env": "CALENDLY_CLIENT_ID",
        "client_secret_env": "CALENDLY_CLIENT_SECRET",
    },
}


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
    client_id, client_secret (any of which may be None if unconfigured).
    """
    auth_config = auth_config or {}
    provider = OAUTH_PROVIDERS.get(slug, {})

    client_id = None
    client_secret = None
    if provider.get("client_id_env"):
        client_id = os.getenv(provider["client_id_env"])
    if provider.get("client_secret_env"):
        client_secret = os.getenv(provider["client_secret_env"])

    # auth_config can override/supply (e.g. self-hosted or per-tenant apps)
    client_id = auth_config.get("client_id") or client_id
    client_secret = auth_config.get("client_secret") or client_secret

    return {
        "authorize_url": auth_config.get("authorize_url") or provider.get("authorize_url"),
        "token_url": auth_config.get("token_url") or provider.get("token_url"),
        "scopes": auth_config.get("scopes") or provider.get("scopes", []),
        "authorize_params": provider.get("authorize_params", {}),
        "client_id": client_id,
        "client_secret": client_secret,
    }
