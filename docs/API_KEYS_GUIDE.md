# API Keys

How a machine authenticates against the Voicecon API: what a key can do, what it
deliberately can't, and how it's enforced.

## What an API key is for

A login token (JWT) belongs to a person and expires in hours. That's wrong for a
customer's backend triggering outbound calls, a CRM sync pulling transcripts, or
a CI script provisioning agents — none of them can sit through an email/password
flow, and none of them should be holding a human's session.

An API key is the credential for those callers: long-lived, bound to one
workspace, revocable on its own without disturbing anyone's login.

Create one under **Settings → API Keys**, or `POST /api/v1/api-keys`. The secret
is returned exactly once; only a bcrypt hash is stored, so a lost key must be
regenerated, never recovered.

## Using a key

Either header works. `Authorization` is canonical; `X-API-Key` exists for
clients that reserve the Authorization header for something else.

```bash
curl https://api.voicecon.com/api/v1/agents \
  -H "Authorization: Bearer vcon_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

curl https://api.voicecon.com/api/v1/agents \
  -H "X-API-Key: vcon_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Every endpoint that accepts a login token accepts a key. Sending both a bearer
key and an `X-API-Key` is a 400 rather than a silent pick.

## How a key is limited

Three limits stack, checked on every request. A key's effective permissions are:

```
role permissions  −  API_KEY_FORBIDDEN  ∩  the key's scopes (if any)
```

### 1. It cannot exceed the person who created it

The key carries no permissions of its own — it borrows the creator's role in the
workspace, re-read from `organization_members` on every request. Demote that
user to viewer and their keys become read-only immediately. Remove them from the
workspace and their keys stop working (**403**), with no rotation needed.

### 2. It is bound to one workspace

A key acts only in the workspace it was minted in. `X-Organization-Id` is
accepted only when it names that same workspace and **403**s otherwise — the
header that lets a browser tab switch workspaces cannot repoint a key.

A key also never moves `users.active_organization_id`. A nightly integration
must not yank the workspace out from under the creator's open browser tab.

### 3. It can be scoped

`scopes` narrows a key past its role. An empty list means "everything the role
allows" — that's the default, and it's still bounded by the two rules above.

```jsonc
// Read-only key for a reporting job
{ "name": "Metabase sync", "scopes": ["calls:read", "analytics:read"] }
```

`GET /api/v1/api-keys/scopes` returns every grantable scope; the Settings UI
builds its picker from that list, so the client can't offer something creation
would reject. An unknown or forbidden scope is a **422** at creation rather than
a key that looks fine and fails later.

## What a key can never do

These require an interactive login regardless of role or scopes
(`permissions.API_KEY_FORBIDDEN`):

| Permission | Why it's withheld |
|---|---|
| `api_keys:manage` | A leaked key must not be able to mint replacements for itself |
| `team:manage`, `team:manage_admins` | A leaked key must not be able to rewrite who has access |
| `billing:manage` | Moving money is a human decision |
| `workspace:delete`, `workspace:transfer_ownership` | A leaked key must not be able to destroy or seize the workspace |

The property being protected: **recovering from a compromised key must never
require that key's cooperation.** An attacker holding a key can misuse the
workspace's data, but cannot lock the real owner out or entrench their access.

Note this means a key can call `GET /api/v1/api-keys` (metadata only, no
secrets) but not `POST`, `PATCH`, `DELETE`, or `regenerate`.

## Managing keys

| Action | Endpoint | Effect |
|---|---|---|
| Create | `POST /api-keys` | Secret returned once |
| List | `GET /api-keys` | Prefixes only, never secrets |
| Grantable scopes | `GET /api-keys/scopes` | What a key may be granted |
| Rename / rescope / set expiry | `PATCH /api-keys/{id}` | Takes effect next request |
| Disable / re-enable | `PATCH /api-keys/{id}` `{"is_active": false}` | Reversible kill switch |
| Rotate | `POST /api-keys/{id}/regenerate` | Old secret dies immediately |
| Revoke | `DELETE /api-keys/{id}` | Permanent |

Managing keys needs `api_keys:manage` (admin and up). Members have
`api_keys:read` and can see the workspace's keys without being able to change
them.

**Expiry** is optional and must be in the future (**422** otherwise). An expired
key authenticates nothing, and the UI labels it `expired` rather than leaving it
looking active.

**Disable vs revoke.** Disabling is the reversible half: the key stops
authenticating right away but can be switched back on. That's what you want
while tracking down which integration a mystery key belongs to. Revoking is
permanent.

## How authentication works

`app/core/api_keys.py`, reached from `get_principal` in `app/core/dependencies.py`:

1. **Route by shape.** A credential starting with `vcon_` is a key; anything
   else is a JWT. No decode is attempted to find out.
2. **Look up by prefix.** `key_prefix` (`vcon_` + 7 chars) is indexed —
   see migration `0014_api_key_prefix_idx`. It is a *lookup hint, not a
   credential*: possessing it proves nothing.
3. **Verify by hash.** Every candidate row is bcrypt-checked against the
   presented secret. The prefix is not unique — 7 characters can collide — so
   multiple candidates must fall through to the hash check rather than error.
4. **Check the key is alive**: active, unexpired, owner active, workspace active.
5. **Record use.** `last_used_at` is written at most once a minute, so a busy
   integration doesn't turn every read into a write.

Every rejection returns the same **401 "Invalid or expired API key"**.
Distinguishing "no such key" from "wrong secret" would hand an attacker an
oracle for enumerating valid prefixes; the real reason is logged server-side.

Authorization then runs through the same `WorkspaceContext.require()` that login
tokens use — there is no parallel permission path for keys to drift out of sync
with. The narrowing happens in one place, `WorkspaceContext.permissions`.

## Error reference

| Status | Meaning |
|---|---|
| 400 | Sent the key as both a bearer token and `X-API-Key` |
| 401 | Key is unknown, wrong, revoked, expired, or its owner is deactivated |
| 403 (`does not permit`) | The creator's role can't do this |
| 403 (`scopes do not include`) | The key's scopes exclude it — widen with `PATCH` |
| 403 (`API keys cannot perform`) | In `API_KEY_FORBIDDEN`; use a signed-in session |
| 403 (`owner no longer has access`) | Creator was removed from the workspace |
| 403 (`cannot act in the workspace named by X-Organization-Id`) | Key is bound elsewhere |
| 422 | Unknown/forbidden scope, past `expires_at`, or empty name |

## Tests

`backend/tests/integration/test_api_key_auth.py` — 34 tests that deliberately do
**not** stub `get_current_user`, so every one exercises the real credential path
against real business endpoints. That's the regression guard: a key that manages
fine but authenticates nothing passes a CRUD-only suite and fails this one.

`backend/tests/integration/test_settings_api.py` covers the management CRUD.

## See also

[Team Workspaces, Roles & Permissions](TEAM_WORKSPACES_GUIDE.md) — the role
matrix a key inherits from.
