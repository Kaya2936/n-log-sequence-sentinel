import unittest

from n_log_sequence_sentinel import Sentinel, SentinelRecord


class FakeClock:
    """Manual clock for deterministic tests."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, amount: float) -> None:
        self.now += amount


class SentinelTests(unittest.TestCase):
    def test_emits_on_threshold_occurrence(self):
        clock = FakeClock()
        s = Sentinel(threshold=3, quiet_timeout=10.0, clock=clock)

        self.assertIsNone(s.observe("disk full"))
        self.assertIsNone(s.observe("disk full"))
        rec = s.observe("disk full")
        self.assertIsInstance(rec, SentinelRecord)
        self.assertEqual(rec, SentinelRecord(message="disk full", count=3))

    def test_returns_none_below_threshold(self):
        clock = FakeClock()
        s = Sentinel(threshold=5, quiet_timeout=10.0, clock=clock)
        for _ in range(4):
            self.assertIsNone(s.observe("oops"))

    def test_suppresses_after_emission(self):
        clock = FakeClock()
        s = Sentinel(threshold=2, quiet_timeout=10.0, clock=clock)

        self.assertIsNone(s.observe("x"))
        self.assertEqual(s.observe("x"), SentinelRecord(message="x", count=2))
        # Further occurrences during the quiet window return None.
        self.assertIsNone(s.observe("x"))
        self.assertIsNone(s.observe("x"))

    def test_resets_after_quiet_timeout(self):
        clock = FakeClock()
        s = Sentinel(threshold=2, quiet_timeout=10.0, clock=clock)

        self.assertIsNone(s.observe("x"))
        self.assertEqual(s.observe("x"), SentinelRecord(message="x", count=2))

        # During quiet window: suppressed.
        clock.advance(5.0)
        self.assertIsNone(s.observe("x"))

        # Past quiet window: resets and re-emits on Nth.
        clock.advance(6.0)
        self.assertIsNone(s.observe("x"))
        self.assertEqual(s.observe("x"), SentinelRecord(message="x", count=2))

    def test_reset_does_not_extend_quiet_window(self):
        clock = FakeClock()
        s = Sentinel(threshold=1, quiet_timeout=10.0, clock=clock)

        # First occurrence emits immediately (threshold == 1).
        self.assertEqual(s.observe("y"), SentinelRecord(message="y", count=1))
        # Occurrence during quiet window is suppressed and does NOT extend.
        clock.advance(5.0)
        self.assertIsNone(s.observe("y"))
        # Still 5 more units to reach 10 from emission time.
        clock.advance(4.0)
        self.assertIsNone(s.observe("y"))
        # Now at 9 + the 5 above = 9 < 10; advancing 1 more crosses 10 from
        # the original emission and the next observe can emit again.
        clock.advance(1.0)
        self.assertEqual(s.observe("y"), SentinelRecord(message="y", count=1))

    def test_messages_are_independent(self):
        clock = FakeClock()
        s = Sentinel(threshold=2, quiet_timeout=10.0, clock=clock)

        self.assertIsNone(s.observe("a"))
        self.assertIsNone(s.observe("b"))
        self.assertEqual(s.observe("a"), SentinelRecord(message="a", count=2))
        self.assertEqual(s.observe("b"), SentinelRecord(message="b", count=2))
        # Both suppressed now.
        self.assertIsNone(s.observe("a"))
        self.assertIsNone(s.observe("b"))

    def test_threshold_one_emits_immediately(self):
        clock = FakeClock()
        s = Sentinel(threshold=1, quiet_timeout=1.0, clock=clock)
        self.assertEqual(s.observe("once"), SentinelRecord(message="once", count=1))
        self.assertIsNone(s.observe("once"))

    def test_exact_timeout_boundary_resets(self):
        clock = FakeClock()
        s = Sentinel(threshold=1, quiet_timeout=10.0, clock=clock)

        self.assertEqual(s.observe("z"), SentinelRecord(message="z", count=1))
        clock.advance(10.0)
        # At exactly quiet_timeout, reset applies (>= comparison).
        self.assertEqual(s.observe("z"), SentinelRecord(message="z", count=1))

    def test_constructor_validates_arguments(self):
        with self.assertRaises(ValueError):
            Sentinel(threshold=0, quiet_timeout=1.0, clock=FakeClock())
        with self.assertRaises(ValueError):
            Sentinel(threshold=1, quiet_timeout=0.0, clock=FakeClock())
        with self.assertRaises(ValueError):
            Sentinel(threshold=1, quiet_timeout=-1.0, clock=FakeClock())

    def test_unhashable_message_raises(self):
        s = Sentinel(threshold=1, quiet_timeout=1.0, clock=FakeClock())
        with self.assertRaises(TypeError):
            s.observe(["mutable", "message"])

    def test_record_is_hashable_and_immutable(self):
        rec = SentinelRecord(message="msg", count=3)
        with self.assertRaises(Exception):
            rec.count = 4  # frozen dataclass
        self.assertEqual(hash(rec), hash(SentinelRecord(message="msg", count=3)))


if __name__ == "__main__":
    unittest.main()
