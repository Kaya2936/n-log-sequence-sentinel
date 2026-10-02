N Log Sequence Sentinel emits a summary record after the Nth occurrence of a given message, then suppresses identical messages until a per-message quiet timeout passes.

Usage:

```python
from n_log_sequence_sentinel import Sentinel, SentinelRecord

sentinel = Sentinel(threshold=3, quiet_timeout=10.0)

for _ in range(3):
    record = sentinel.observe("disk full")
    if record is not None:
        print(f"{record.message} happened {record.count} times")
```

The library exists to turn a flood of identical log lines into a single summary at a chosen threshold. The trade-off is suppression keyed per message: after the Nth occurrence, further identical messages are dropped until quiet_timeout units of clock time elapse without any occurrence of that message. A global quiet window would interleave badly with unrelated messages; per-message is simpler and predictable.

Edge to be aware of: occurrences during the quiet window do not extend the window. The window is measured from the emitted record, not the most recent suppressed occurrence. The quiet boundary is inclusive: an occurrence exactly quiet_timeout units after emission resets the counter. Messages must be hashable; unhashable values raise TypeError immediately.
