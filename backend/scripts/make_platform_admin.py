"""
Grant (or revoke) platform-admin access for an existing account.

    python -m scripts.make_platform_admin you@company.com
    python -m scripts.make_platform_admin you@company.com --revoke

The account must already exist (sign up first). On a deployment where running a
script is awkward, set PLATFORM_ADMIN_EMAILS=you@company.com instead; the API
promotes those addresses when it starts.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth.verification import normalize_email  # noqa: E402


async def main(email: str, revoke: bool) -> int:
    email = normalize_email(email)
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No account with email {email}. Sign up first.")
            return 1
        if revoke:
            admins = (await db.execute(select(func.count(User.id)).where(User.is_platform_admin.is_(True)))).scalar()
            if user.is_platform_admin and admins <= 1:
                print("Refusing: this is the last platform admin.")
                return 1
        user.is_platform_admin = not revoke
        await db.commit()
    print(f"{email} is {'no longer' if revoke else 'now'} a platform admin.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.email, args.revoke)))
