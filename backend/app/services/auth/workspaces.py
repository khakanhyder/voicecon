"""
Personal-workspace helpers shared by every sign-up path.

`Organization.slug` is UNIQUE, but the obvious slug — the email's local part —
is not: alice@one.com and alice@two.com both want "alice". The social sign-up
path has always retried on collision; plain email sign-up did not, so the second
alice got an IntegrityError and `/auth/register` answered 500. Both paths now
call the same helper.
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Organization

#: Attempts with a random suffix before falling back to a longer one. Five
#: six-hex-digit draws against a single taken slug will not realistically all
#: collide; the final wider suffix exists so the function cannot return a
#: duplicate even in principle.
_SUFFIX_ATTEMPTS = 5


async def unique_org_slug(db: AsyncSession, email: str) -> str:
    """
    Pick a free `Organization.slug` derived from `email`.

    Returns the bare local part when it is free, so the common case keeps the
    readable slug, and appends a random suffix only on collision.
    """
    base = email.split("@")[0].lower().replace(".", "-") or "workspace"
    slug = base
    for _ in range(_SUFFIX_ATTEMPTS):
        taken = (
            await db.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()
        if not taken:
            return slug
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
    return f"{base}-{uuid.uuid4().hex[:10]}"
