"""
Re-encrypt stored integration credentials under a new encryption key.

Why this exists
---------------
``credential_manager`` used to fall back to a secret hardcoded in the source
tree when ``ENCRYPTION_SECRET_KEY`` was unset, paired with a hardcoded salt.
Any deployment that never set the variable therefore encrypted every tenant's
OAuth tokens and per-connection API keys under a key that anyone with a copy of
this repository can reconstruct. The ciphertext in those columns offers no real
protection against a database dump.

Setting a real key does not fix the existing rows — it makes them undecryptable,
because the key that produced them no longer matches. This script bridges that:
it reads each value with the *old* key and rewrites it with the *new* one.

Usage
-----
Dry run first — reports what would change, writes nothing::

    python -m scripts.reencrypt_credentials

Then, once the counts look right::

    python -m scripts.reencrypt_credentials --commit

By default the old key is the public legacy default, which is the case this was
written for. If you are rotating away from a key you had already set properly,
pass it explicitly::

    OLD_ENCRYPTION_SECRET_KEY=... OLD_ENCRYPTION_SALT=... \
        python -m scripts.reencrypt_credentials --commit

The new key is read from the ordinary ``ENCRYPTION_SECRET_KEY`` /
``ENCRYPTION_SALT`` settings, so set those in the environment *before* running.

Safety
------
* Take a database backup first. This rewrites credential columns in place.
* A row that fails to decrypt under the old key is reported and left untouched,
  never blanked — a value that cannot be read is still better than one that has
  been destroyed.
* Re-running is safe. A row already written under the new key fails the old-key
  decrypt, gets counted as "already migrated", and is skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.integration import IntegrationConnection
from app.services.integrations.credential_manager import (
    LEGACY_DEFAULT_SECRET,
    LEGACY_SALT,
    derive_key,
)
from app.core.config import settings


#: The columns holding ciphertext produced by ``CredentialManager.encrypt``.
CREDENTIAL_COLUMNS = (
    "auth_data_encrypted",
    "api_key_encrypted",
    "access_token_encrypted",
    "refresh_token_encrypted",
)


@dataclass
class Report:
    rows_seen: int = 0
    values_rewritten: int = 0
    values_already_new: int = 0
    values_empty: int = 0
    failures: list[str] = field(default_factory=list)

    def render(self, committed: bool) -> str:
        mode = "COMMITTED" if committed else "DRY RUN — nothing was written"
        lines = [
            "",
            f"  Connections examined     {self.rows_seen}",
            f"  Values re-encrypted      {self.values_rewritten}",
            f"  Already on the new key   {self.values_already_new}",
            f"  Empty / unset            {self.values_empty}",
            f"  Failed                   {len(self.failures)}",
            "",
            f"  {mode}",
        ]
        if self.failures:
            lines += ["", "  Could not decrypt under either key:"]
            lines += [f"    - {f}" for f in self.failures]
            lines += [
                "",
                "  These rows were left untouched. They were most likely written",
                "  under a third key; the owning customer will need to reconnect",
                "  the integration.",
            ]
        return "\n".join(lines)


def _old_cipher() -> Fernet:
    """Cipher for the key the existing ciphertext was written under."""
    secret = os.getenv("OLD_ENCRYPTION_SECRET_KEY", LEGACY_DEFAULT_SECRET)

    raw_salt = os.getenv("OLD_ENCRYPTION_SALT")
    if raw_salt:
        try:
            salt = bytes.fromhex(raw_salt)
        except ValueError:
            salt = raw_salt.encode()
    else:
        salt = LEGACY_SALT

    return Fernet(derive_key(secret, salt))


def _new_cipher() -> Fernet:
    """Cipher for the key we are moving to, from the live settings."""
    secret = settings.ENCRYPTION_SECRET_KEY or os.getenv("ENCRYPTION_SECRET_KEY")
    if not secret:
        sys.exit(
            "ENCRYPTION_SECRET_KEY is not set. Set the NEW key in the environment "
            "before running this script."
        )
    if secret == LEGACY_DEFAULT_SECRET:
        sys.exit(
            "ENCRYPTION_SECRET_KEY is still the public legacy default. Generate a "
            "real one with:\n"
            '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    raw_salt = settings.ENCRYPTION_SALT or os.getenv("ENCRYPTION_SALT")
    if not raw_salt:
        sys.exit(
            "ENCRYPTION_SALT is not set. Generate one with:\n"
            '  python -c "import secrets; print(secrets.token_hex(16))"'
        )
    try:
        salt = bytes.fromhex(raw_salt)
    except ValueError:
        salt = raw_salt.encode()

    return Fernet(derive_key(secret, salt))


def _rotate_value(
    value: Optional[str],
    old: Fernet,
    new: Fernet,
    label: str,
    report: Report,
) -> Optional[str]:
    """Return the value re-encrypted under ``new``, or None to leave it alone."""
    if not value:
        report.values_empty += 1
        return None

    try:
        plaintext = old.decrypt(value.encode())
    except (InvalidToken, ValueError):
        # Either already migrated, or written under a key we don't have. Tell
        # those apart by trying the new key — only the second is a real failure.
        try:
            new.decrypt(value.encode())
            report.values_already_new += 1
        except (InvalidToken, ValueError):
            report.failures.append(label)
        return None

    report.values_rewritten += 1
    return new.encrypt(plaintext).decode()


async def reencrypt(commit: bool) -> Report:
    old, new = _old_cipher(), _new_cipher()
    report = Report()

    async with AsyncSessionLocal() as db:
        connections = (
            await db.execute(select(IntegrationConnection))
        ).scalars().all()

        for conn in connections:
            report.rows_seen += 1
            for column in CREDENTIAL_COLUMNS:
                rotated = _rotate_value(
                    getattr(conn, column),
                    old,
                    new,
                    label=f"connection {conn.id} · {column}",
                    report=report,
                )
                if rotated is not None:
                    setattr(conn, column, rotated)

        if commit:
            await db.commit()
        else:
            await db.rollback()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-encrypt integration credentials under a new key."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write the changes. Without this the script only reports.",
    )
    args = parser.parse_args()

    if args.commit:
        print("Re-encrypting credentials. Make sure you have a database backup.\n")

    report = asyncio.run(reencrypt(commit=args.commit))
    print(report.render(committed=args.commit))

    if not args.commit and report.values_rewritten:
        print("\n  Re-run with --commit to apply.\n")

    sys.exit(1 if report.failures else 0)


if __name__ == "__main__":
    main()
