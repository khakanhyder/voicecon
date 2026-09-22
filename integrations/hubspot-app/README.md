# Voicecon HubSpot public app

HubSpot disabled public-app creation in the developer UI (Legacy Apps → Public is
greyed out), so the app that backs the `hubspot` connector is defined here and
pushed with the HubSpot CLI instead.

`requiredScopes` must stay in sync with the scopes the backend requests —
`auth_config.scopes` on the `hubspot` row in `integration_connectors`, seeded from
`backend/scripts/seed_data.py`. HubSpot fails the authorize step outright on any
scope the app does not have.

## Push changes

```bash
npm install -g @hubspot/cli@latest   # needs v7.6.0+
hs account auth                      # opens a browser; pick developer account 246755024
cd integrations/hubspot-app
hs project upload
hs project open                      # Auth tab → Client credentials
```

Copy the Client ID / Client Secret into `HUBSPOT_CLIENT_ID` / `HUBSPOT_CLIENT_SECRET`
(Dokploy env, or /admin → Integration OAuth apps, which overrides env).

To test the flow against a local backend, add the local callback to `redirectUrls`
and re-upload — HubSpot rejects a redirect_uri that is not listed verbatim.
