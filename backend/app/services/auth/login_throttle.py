"""
Failed-login throttling, keyed by the account being targeted.

This is the rule that actually stops password guessing. The rate-limit
middleware keys anonymous traffic by IP, which an attacker rotates and an
office shares, so it can only ever be a coarse ceiling — whereas an attacker
guessing one person's password must keep naming that one address, and counting
per address catches them however many IPs they come from.

Scope, stated plainly: the counters live in this process. With several replicas
behind a load balancer an attacker gets the allowance once per replica, so this
raises the cost of guessing rather than capping it absolutely. Making it exact
means moving the counter to Redis or a column on `users`; both were larger
changes than the fix warranted, and neither is required for the limit to bite.

Only *failed* attempts count, and a success clears the record, so someone who
mistypes a password twice and then gets it right is never affected. Completing
a password reset clears it too — proving control of the address is a stronger
signal than the failures that came before it, and without that a user who
reset *because* they were locked out would be refused at the login form with a
password they had just chosen.

The accepted trade-off: because the counter is keyed on the address alone,
someone who knows a victim's email can hold that account locked with five
cheap requests every fifteen minutes. That is inherent to per-account
lockout, and the alternatives are worse — keying on address *and* IP lets an
attacker rotate IPs and guess forever, which is the attack this exists to
stop. The window is deliberately short, and the real fix when it matters is
step-up verification (a CAPTCHA or an emailed code) rather than a longer lock.
"""
import time
from collections import defaultdict
from typing import Dict, List

from app.core.config import settings

#: address -> timestamps of recent failures.
_failures: Dict[str, List[float]] = defaultdict(list)

#: Drop addresses nothing has touched in a while, so the dict cannot grow once
#: per address ever guessed at.
_PRUNE_EVERY_SECONDS = 300
_last_prune = 0.0


def _window() -> int:
    return settings.RATE_LIMIT_LOGIN_LOCKOUT_SECONDS


def _prune(now: float) -> None:
    global _last_prune
    if now - _last_prune < _PRUNE_EVERY_SECONDS:
        return
    _last_prune = now
    cutoff = now - _window()
    for email in [e for e, ts in _failures.items() if not any(t > cutoff for t in ts)]:
        del _failures[email]


def seconds_until_unlocked(email: str) -> int:
    """
    How long this address must wait, or 0 if it may attempt a login now.

    Checked *before* the password is verified, so a locked account costs an
    attacker nothing to probe — and, importantly, costs the server no bcrypt
    round either, which is what makes a flood of guesses expensive to absorb.
    """
    now = time.time()
    _prune(now)

    cutoff = now - _window()
    recent = [ts for ts in _failures.get(email, []) if ts > cutoff]
    if not recent:
        _failures.pop(email, None)
        return 0
    _failures[email] = recent

    if len(recent) < settings.RATE_LIMIT_LOGIN_ATTEMPTS:
        return 0
    return max(1, int(recent[0] + _window() - now))


def record_failure(email: str) -> None:
    """Count one failed attempt against an address."""
    now = time.time()
    _prune(now)
    _failures[email].append(now)


def clear(email: str) -> None:
    """Forget an address's failures, called on a successful sign-in."""
    _failures.pop(email, None)


def reset_all() -> None:
    """Drop every counter. For tests that need a clean slate."""
    _failures.clear()
