"""Per-client rate limiting for link creation.

Creating links is the expensive, abusable operation: unchecked it grows the database and
eats the code space. The allowance is counted per client inside a moving time window.

Clients are identified by a salted hash of their address rather than the address itself,
so no raw IP is held even in memory. The salt is generated per process, which also means
the keys are meaningless outside the run that produced them.

State lives in this process. Several replicas would each enforce their own allowance, so
a real deployment needs a shared store such as Redis.
"""

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

_SALT = secrets.token_bytes(16)


def client_key(address: str) -> str:
    """Return a stable, non-reversible identifier for a client address."""
    return hashlib.blake2b(address.encode(), key=_SALT, digest_size=16).hexdigest()


@dataclass
class SlidingWindowRateLimiter:
    """Allows a fixed number of requests per client inside a moving window."""

    limit: int
    window_seconds: int
    _hits: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, client: str, now: float | None = None) -> bool:
        """Record a request and report whether it falls within the allowance."""
        moment = time.monotonic() if now is None else now
        cutoff = moment - self.window_seconds

        hits = self._hits.get(client)
        if hits is None:
            hits = deque()
            self._hits[client] = hits

        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self.limit:
            return False

        hits.append(moment)
        self._forget_idle_clients(cutoff)
        return True

    def _forget_idle_clients(self, cutoff: float) -> None:
        """Drop clients whose window has emptied, so the map does not grow forever."""
        idle = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in idle:
            del self._hits[key]
