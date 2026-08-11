"""
Unit tests for per-account failed-login throttling.

This is the control that actually stops password guessing: the IP-keyed rate
limiter is a coarse ceiling an attacker rotates around, but a guesser must keep
naming the one address they are attacking, and this counts that.

Time is driven by monkeypatching `time.time` rather than sleeping, so the
15-minute window is exercised in milliseconds. `reset_all()` runs before every
test because the counters are module-level and would otherwise leak between
tests.
"""
import pytest

from app.core.config import settings
from app.services.auth import login_throttle
from app.services.auth.login_throttle import (
    clear,
    record_failure,
    reset_all,
    seconds_until_unlocked,
)

VICTIM = "victim@example.com"
BYSTANDER = "bystander@example.com"


@pytest.fixture(autouse=True)
def clean_counters():
    """The failure counters are process-global; isolate every test from them."""
    reset_all()
    yield
    reset_all()


@pytest.fixture
def clock(monkeypatch):
    """A controllable `time.time`, so the lockout window is testable instantly."""

    class Clock:
        def __init__(self):
            self.now = 1_000_000.0

        def advance(self, seconds):
            self.now += seconds

    fake = Clock()
    monkeypatch.setattr(login_throttle.time, "time", lambda: fake.now)
    # The pruning pass is time-based too, and its "last pruned" marker survives
    # between tests; reset it so a jump backwards in fake time still prunes.
    monkeypatch.setattr(login_throttle, "_last_prune", 0.0)
    return fake


def _limit() -> int:
    return settings.RATE_LIMIT_LOGIN_ATTEMPTS


def _window() -> int:
    return settings.RATE_LIMIT_LOGIN_LOCKOUT_SECONDS


@pytest.mark.unit
@pytest.mark.auth
class TestLockout:
    def test_a_fresh_address_is_not_locked(self):
        assert seconds_until_unlocked(VICTIM) == 0

    def test_failures_below_the_limit_do_not_lock(self, clock):
        """Someone mistyping their password must not be locked out for it."""
        for _ in range(_limit() - 1):
            record_failure(VICTIM)

        assert seconds_until_unlocked(VICTIM) == 0

    def test_the_limit_locks_the_account(self, clock):
        for _ in range(_limit()):
            record_failure(VICTIM)

        assert seconds_until_unlocked(VICTIM) > 0

    def test_the_wait_is_reported_in_seconds_within_the_window(self, clock):
        for _ in range(_limit()):
            record_failure(VICTIM)

        wait = seconds_until_unlocked(VICTIM)

        assert 0 < wait <= _window()

    def test_the_wait_counts_down_as_time_passes(self, clock):
        for _ in range(_limit()):
            record_failure(VICTIM)
        first = seconds_until_unlocked(VICTIM)

        clock.advance(60)

        assert seconds_until_unlocked(VICTIM) < first

    def test_the_lock_expires_when_the_window_passes(self, clock):
        for _ in range(_limit()):
            record_failure(VICTIM)
        assert seconds_until_unlocked(VICTIM) > 0

        clock.advance(_window() + 1)

        assert seconds_until_unlocked(VICTIM) == 0

    def test_a_locked_account_never_reports_zero_while_locked(self, clock):
        """
        Rounding down to 0 would tell the caller "try now" while the account is
        still locked, producing a login form that refuses a correct password
        with no explanation.
        """
        for _ in range(_limit()):
            record_failure(VICTIM)

        clock.advance(_window() - 0.4)  # a sliver of the window left

        assert seconds_until_unlocked(VICTIM) >= 1


@pytest.mark.unit
@pytest.mark.auth
class TestWindowIsSliding:
    def test_failures_that_age_out_stop_counting(self, clock):
        """
        Four failures now and one in fifteen minutes is not an attack, and must
        not lock the account.
        """
        for _ in range(_limit() - 1):
            record_failure(VICTIM)

        clock.advance(_window() + 1)
        record_failure(VICTIM)

        assert seconds_until_unlocked(VICTIM) == 0

    def test_sustained_guessing_across_the_window_still_locks(self, clock):
        """Spacing guesses out only helps if they fall outside the window."""
        for _ in range(_limit()):
            record_failure(VICTIM)
            clock.advance(1)

        assert seconds_until_unlocked(VICTIM) > 0


@pytest.mark.unit
@pytest.mark.auth
class TestScope:
    def test_counters_are_per_address(self, clock):
        """
        Locking one account must not lock anybody else's — otherwise a single
        attacker could take the whole login page down.
        """
        for _ in range(_limit() * 2):
            record_failure(VICTIM)

        assert seconds_until_unlocked(VICTIM) > 0
        assert seconds_until_unlocked(BYSTANDER) == 0

    def test_addresses_are_matched_exactly(self, clock):
        """
        Documents that the key is the raw string the caller passes. Callers must
        normalise the address themselves, or `User@x.com` and `user@x.com` would
        each get their own allowance.
        """
        for _ in range(_limit()):
            record_failure(VICTIM)

        assert seconds_until_unlocked(VICTIM.upper()) == 0


@pytest.mark.unit
@pytest.mark.auth
class TestClearing:
    def test_a_successful_sign_in_clears_the_failures(self, clock):
        """Mistyping twice then getting it right must leave no trace."""
        for _ in range(_limit() - 1):
            record_failure(VICTIM)

        clear(VICTIM)

        for _ in range(_limit() - 1):
            record_failure(VICTIM)
        assert seconds_until_unlocked(VICTIM) == 0

    def test_clearing_unlocks_a_locked_account(self, clock):
        """
        Completing a password reset clears the counter: proving control of the
        address outranks the failures before it. Without this, a user who reset
        *because* they were locked out would still be refused.
        """
        for _ in range(_limit()):
            record_failure(VICTIM)
        assert seconds_until_unlocked(VICTIM) > 0

        clear(VICTIM)

        assert seconds_until_unlocked(VICTIM) == 0

    def test_clearing_an_unknown_address_is_a_no_op(self):
        clear("nobody@example.com")

        assert seconds_until_unlocked("nobody@example.com") == 0

    def test_reset_all_drops_every_counter(self, clock):
        for _ in range(_limit()):
            record_failure(VICTIM)
            record_failure(BYSTANDER)

        reset_all()

        assert seconds_until_unlocked(VICTIM) == 0
        assert seconds_until_unlocked(BYSTANDER) == 0


@pytest.mark.unit
@pytest.mark.auth
class TestMemoryGrowth:
    def test_stale_addresses_are_pruned(self, clock):
        """
        The counter dict is keyed by address, so without pruning an attacker
        spraying random addresses would grow it once per address forever.
        """
        for i in range(50):
            record_failure(f"sprayed-{i}@example.com")
        assert len(login_throttle._failures) == 50

        # Past the window and past the prune interval, then touch it once.
        clock.advance(_window() + login_throttle._PRUNE_EVERY_SECONDS + 1)
        record_failure(VICTIM)

        assert len(login_throttle._failures) == 1

    def test_pruning_keeps_addresses_that_are_still_within_the_window(self, clock):
        for i in range(10):
            record_failure(f"active-{i}@example.com")

        clock.advance(login_throttle._PRUNE_EVERY_SECONDS + 1)
        record_failure(VICTIM)

        # Still inside the lockout window, so none of them may be forgotten.
        assert len(login_throttle._failures) == 11
