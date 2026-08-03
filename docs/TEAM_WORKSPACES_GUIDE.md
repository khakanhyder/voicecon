# Team Workspaces, Roles & Permissions

How a user works inside a shared workspace, how they move between workspaces,
and exactly what each role may do.

## The model

An **Organization** is a workspace. Every user gets one at sign-up (they own
it), and can belong to any number of others through invitations. Membership and
role live in `organization_members`; a user has one row per workspace, each with
its own role.

**Resources belong to the workspace, not to the person who created them.**
Agents, calls, phone numbers, workflows, tools, knowledge bases, and integration
connections are all scoped by `organization_id`. `user_id` on those tables
records authorship only — it is never used for access control. That is what lets
an invited teammate open an agent a colleague built.

## Which workspace is a request acting in?

Resolved once per request by `app/core/workspace.py`, first match wins:

1. **`X-Organization-Id` header** — an explicit per-request override. The
   frontend sends it on every call. A header naming a workspace the caller
   doesn't belong to is a hard **403**; it never silently falls back, so a stale
   tab can't quietly read the wrong workspace.
2. **`users.active_organization_id`** — the workspace they last switched to.
3. **A deterministic default** — the workspace they own, else the one they
   joined first.

The resolved value is written back to `active_organization_id`, so a pointer
that goes stale (membership revoked, workspace deactivated) heals itself on the
next request instead of 404-ing forever.

`active_organization_id` has no database foreign key on purpose: `organizations.
owner_id` already points at `users`, and closing that cycle would force
ALTER-based schema create/drop. Membership is re-validated on every request
anyway, which is stronger than referential integrity — it also catches a
membership that was revoked while the workspace still exists.

## Roles

`owner > admin > member > viewer`. The full matrix lives in
`app/core/permissions.py` and is served to the frontend by
`GET /api/v1/workspaces/current`, so there is only ever one copy of it.

| | Viewer | Member | Admin | Owner |
|---|---|---|---|---|
| View agents, calls, analytics | ✅ | ✅ | ✅ | ✅ |
| Create/edit/delete agents, workflows, tools, knowledge | — | ✅ | ✅ | ✅ |
| Buy phone numbers, connect integrations | — | ✅ | ✅ | ✅ |
| Invite members & viewers, change their roles, remove them | — | — | ✅ | ✅ |
| Create API keys | — | — | ✅ | ✅ |
| Rename the workspace | — | — | ✅ | ✅ |
| View billing | — | — | ✅ | ✅ |
| **Invite or promote an admin** | — | — | — | ✅ |
| **Act on an admin or the owner** | — | — | — | ✅ |
| **Change plan / manage billing** | — | — | — | ✅ |
| **Transfer ownership** | — | — | — | ✅ |
| **Delete the workspace** | — | — | — | ✅ |

Permissions are *not* purely hierarchical. Everything that moves power inside a
workspace is withheld from admins, which is what stops an admin from taking one
over. Concretely, an admin cannot:

- demote or remove the owner (403 / 400),
- remove or demote a fellow admin,
- promote anyone — including themselves — to admin or owner,
- invite someone as an admin,
- transfer ownership or delete the workspace,
- change their own role.

Ownership moves only through `POST /workspaces/current/transfer-ownership`,
which is owner-only. It promotes the target and demotes the outgoing owner to
admin in one transaction, so the workspace always has exactly one owner and
`organizations.owner_id` can never disagree with the membership rows.

## Enforcement

Two independent layers, both server-side:

1. **Router-level guard.** `app/api/v1/api.py` attaches
   `workspace_guard(read_permission, write_permission)` to every
   workspace-scoped router. Safe methods (`GET`/`HEAD`/`OPTIONS`) need the read
   permission, everything else the write one. A newly added endpoint is
   protected by default rather than by the author remembering to protect it.
2. **Endpoint checks.** Anything finer — team management, ownership, billing —
   adds `Depends(require_permission(...))` and the rank checks in
   `team.py`/`workspaces.py`.

Genuinely public routes (carrier webhooks, the Stripe webhook, the embeddable
chat widget, the marketplace catalogue) live on a separate `public_router` in
their module and are mounted without the guard.

The frontend hides controls the caller can't use, driven by the same permission
strings. That is presentation only — the API refuses the request either way.

## API

| Method | Path | Who |
|---|---|---|
| `GET` | `/api/v1/workspaces` | any member — never 404s, so you can always switch out |
| `GET` | `/api/v1/workspaces/current` | any member — role + full permission list |
| `POST` | `/api/v1/workspaces` | any user — creates and switches into a new workspace |
| `POST` | `/api/v1/workspaces/{id}/switch` | any member of `{id}` |
| `PATCH` | `/api/v1/workspaces/current` | admin+ (rename) |
| `POST` | `/api/v1/workspaces/current/transfer-ownership` | owner |
| `POST` | `/api/v1/workspaces/current/leave` | any member except the owner |
| `DELETE` | `/api/v1/workspaces/current` | owner, and never their last workspace |
| `GET` | `/api/v1/team/members` | any member |
| `POST` | `/api/v1/team/invite` | admin+ (owner only for the `admin` role) |
| `GET`/`DELETE` | `/api/v1/team/invitations[/{id}]` | admin+ |
| `PATCH`/`DELETE` | `/api/v1/team/members/{id}` | admin+, subject to the rank rules |

`GET /workspaces`, `POST /workspaces/{id}/switch`, and `POST /workspaces`
deliberately do **not** depend on the current workspace, so a user who was just
removed from their active one can still list and switch.

## Invitation flow

1. An admin/owner invites an email. A pending `Invitation` is created — not a
   membership — so pending invites never appear in the member list. An email
   with Accept/Decline links goes out, plus an in-app notification if the
   address already has an account.
2. The invitee opens `/invite/{token}`, signing in or registering as needed.
   The signed-in email must match the invited address.
3. On accept, the membership is created **and their active workspace is set to
   the workspace they just joined**. Their next request is inside the shared
   workspace, not their personal one — without this the invitation appears to do
   nothing. `POST /invitations/{token}/accept` returns `organization_id` so the
   client can pin it immediately.
4. Invites expire after 7 days; accepting an expired, canceled, or already-used
   invite is a 400, and a replayed accept can't create a duplicate membership.

## Switching in the UI

The sidebar switcher (`WorkspaceSwitcher`) lists every workspace with the
caller's role and member count. Switching stores the id in `localStorage` under
`active_organization_id`, which the axios interceptor sends as
`X-Organization-Id` on every request, then reloads the page — every list on
screen is workspace-scoped, so a reload is the honest way to clear stale data.

The pin is cleared on login, logout, and account deletion so one user's
workspace never leaks into the next session. If a request 403s because the
pinned workspace is gone, the interceptor drops the pin and retries once, and
the server picks a workspace the user still belongs to.

## Tests

- `backend/tests/unit/test_permissions.py` — the matrix itself: hierarchy,
  supersets, and the capabilities an admin must never gain.
- `backend/tests/integration/test_workspaces_api.py` — resolution, switching,
  header override, data scoping across workspaces, per-role permissions, every
  owner-only escalation attempt, and the full invitation journey.

Run them with the project's usual overrides:

```bash
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://voicecon_user:voicecon_password_dev@localhost:5435/voicecon_test" \
  ./venv/bin/python -m pytest tests/unit/test_permissions.py tests/integration/test_workspaces_api.py \
  -o addopts="" -p no:postgresql -p no:xdist -p no:logging -p no:cacheprovider -q
```
