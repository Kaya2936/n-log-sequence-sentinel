"""Core implementation of the N Log Sequence Sentinel.

The sentinel counts occurrences of a message and emits a summary record on the
Nth occurrence. After emitting, identical messages are suppressed until a quiet
timeout passes without any occurrence of that message.

Design decisions
-----------------
- The quiet window is keyed by the message itself. While "a quiet period globally"
might seem natural, per-message suppression is what prevents a runaway log line
from spamming every summary. One clear choice over a global quiet that would
interact oddly with interleaved messages.
- Suppression is evaluated in terms of the clock supplied at construction. Tests
inject a fake clock so assertions are deterministic.
- Record equality and dict keys rely on the hashability of the message. This is
documented; callers passing unhashable messages get a TypeError immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Hashable, Optional


@dataclass(frozen=True)
class SentinelRecord:
    """Summary record emitted on the Nth occurrence of a message.

    Attributes:
        message: The message that triggered the summary.
        count: How many times it occurred at the moment of emission.
    """

    message: object
    count: int


class Sentinel:
    """Emit a summary record after the Nth occurrence of a message, then
    suppress identical messages until a quiet timeout passes.

    Args:
        threshold: Emit on the Nth occurrence where N == threshold. Must be >= 1.
        quiet_timeout: Suppress for this many clock units after the Nth
            occurrence. After this many units pass without an occurrence, the
            message resets and can again reach its threshold. Must be > 0.
        clock: Zero-argument callable returning a number. Defaults to
            time.monotonic so the default is usable in production and still
            injectable in tests.

    Raises:
        ValueError: If threshold < 1 or quiet_timeout <= 0.
    """

    def __init__(
        self,
        threshold: int,
        quiet_timeout: float,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if quiet_timeout <= 0:
            raise ValueError("quiet_timeout must be > 0")
        self.threshold = threshold
        self.quiet_timeout = quiet_timeout
        # Import locally so the module does not require time at import time in
        # odd environments; it is only the default fallback.
        if clock is None:
            import time

            clock = time.monotonic
        self._clock = clock
        self._counts: Dict[Hashable, int] = {}
        self._last_emission: Dict[Hashable, float] = {}

    def _reset_if_quiet(self, message: Hashable, now: float) -> None:
        """Reset the count for a message if the quiet timeout has elapsed since
        its last emission.

        If the message has never been emitted, nothing happens.
        """
        emission_time = self._last_emission.get(message)
        if emission_time is not None and (now - emission_time) >= self.quiet_timeout:
            # The quiet window passed with no occurrences. Reset the message so
            # it can accumulate again from zero.
            self._counts.pop(message, None)
            self._last_emission.pop(message, None)

    def observe(self, message: Hashable) -> Optional[SentinelRecord]:
        """Record an occurrence of message.

        Returns a SentinelRecord exactly when this is the Nth occurrence
        (where N == threshold). Returns None otherwise, including when the
        message is currently suppressed.

        Args:
            message: Hashable message key.

        Raises:
            TypeError: If message is unhashable.
        """
        now = self._clock()
        self._reset_if_quiet(message, now)

        if message in self._last_emission:
            # Suppressed. The check after _reset_if_quiet guarantees we are
            # still within the quiet window relative to the most recent
            # emission; occurrences do not extend the window.
            return None

        count = self._counts.get(message, 0) + 1
        self._counts[message] = count

        if count == self.threshold:
            self._last_emission[message] = now
            return SentinelRecord(message=message, count=count)

        return None
