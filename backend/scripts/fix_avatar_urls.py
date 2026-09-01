"""
Repair avatar URLs stored with the wrong scheme.

Before app/core/urls.py existed, a deployment behind a TLS-terminating proxy
wrote avatar URLs as ``http://api.example.com/uploads/...`` — the scheme the app
saw on its own connection, not the one the browser used. Those rows still point
at http, so the picture keeps rendering broken on an https dashboard even after
the code is fixed; only a re-upload would rewrite them.

Rewrites the scheme in place. Idempotent, and touches only URLs on this API's
own origin — an avatar hosted on a Google or GitHub CDN is left alone.

Run:  python -m scripts.fix_avatar_urls          (from backend/)
      python -m scripts.fix_avatar_urls --dry-run

Requires API_BASE_URL to be set, since that is the only statement of what this
API's public origin is that does not depend on an incoming request.
"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database import DATABASE_URL
from app.models.user import User


async def main(dry_run: bool) -> int:
    base = (settings.API_BASE_URL or "").rstrip("/")
    if not base:
        print("API_BASE_URL is not set — nothing to compare stored URLs against.")
        print("Set it to this API's public origin (e.g. https://api.example.com).")
        return 1

    parsed = urlsplit(base)
    if parsed.scheme != "https":
        print(f"API_BASE_URL is {base!r}, which is not https — nothing to fix.")
        return 0

    wrong_prefix = f"http://{parsed.netloc}/"
    right_prefix = f"https://{parsed.netloc}/"

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    fixed = 0
    async with session_factory() as db:
        users = (
            await db.execute(
                select(User).where(User.avatar_url.like(f"{wrong_prefix}%"))
            )
        ).scalars().all()

        for user in users:
            updated = right_prefix + user.avatar_url[len(wrong_prefix):]
            print(f"{user.email}: {user.avatar_url} -> {updated}")
            if not dry_run:
                user.avatar_url = updated
            fixed += 1

        if fixed and not dry_run:
            await db.commit()

    await engine.dispose()
    print(f"{fixed} avatar URL(s) {'would be ' if dry_run else ''}updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--dry-run" in sys.argv)))
