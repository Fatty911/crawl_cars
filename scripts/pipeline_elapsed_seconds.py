"""Measure elapsed CNB build time from its documented start timestamp."""
from datetime import datetime, timezone
import os
import time


def elapsed_seconds(start, now=None):
    if not start:
        raise ValueError('CNB_BUILD_START_TIME is missing; refusing an unbounded allocation')
    now = time.time() if now is None else now
    try:
        stamp = float(start)
        if stamp > 1e11:
            stamp /= 1000
    except ValueError:
        parsed = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        stamp = parsed.timestamp()
    return max(0, int(now - stamp))


if __name__ == '__main__':
    print(elapsed_seconds(os.environ.get('CNB_BUILD_START_TIME')))
