"""
velocity.py — streaming velocity features backed by Redis.

Training-time feature contract (ml_models/train_fraud_model.py):
  tx_count_5m          prior txs in the last 300 s (excludes the current one)
  tx_sum_24h           sum of prior tx amounts in the last 86400 s
  amount_to_avg_ratio  amount / median(last <=50 prior amounts); 1.0 if < 3 prior

A single Lua script reads those windows AND appends the current transaction
atomically in one round trip. Doing the append inline (instead of in a Celery
task) is deliberate: a card-testing burst lands seconds apart, so an
asynchronous window update would let the 2nd..Nth probe score against stale
state, which is exactly the signal the model relies on. Celery still owns the
heavy work (embeddings, budgets, analytics).

Keys use a {user_id} hash tag so both keys live in the same Redis Cluster slot.
"""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

_LUA = """
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 86400)
local c5 = redis.call('ZCOUNT', KEYS[1], now - 300, '+inf')
local members = redis.call('ZRANGEBYSCORE', KEYS[1], now - 86400, '+inf')
local sum = 0
for _, m in ipairs(members) do
  local a = string.match(m, ':([%d%.]+)$')
  if a then sum = sum + tonumber(a) end
end
local hist = redis.call('LRANGE', KEYS[2], 0, 49)
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], 90000)
redis.call('LPUSH', KEYS[2], ARGV[2])
redis.call('LTRIM', KEYS[2], 0, 49)
redis.call('EXPIRE', KEYS[2], 2592000)
local out = {tostring(c5), string.format('%.2f', sum)}
for _, h in ipairs(hist) do out[#out + 1] = h end
return out
"""

# Read-only twin of the script above: identical feature maths, but it never writes (used by the live preview).
_LUA_PEEK = """
local now = tonumber(ARGV[1])
local c5 = redis.call('ZCOUNT', KEYS[1], now - 300, '+inf')
local members = redis.call('ZRANGEBYSCORE', KEYS[1], now - 86400, '+inf')
local sum = 0
for _, m in ipairs(members) do
  local a = string.match(m, ':([%d%.]+)$')
  if a then sum = sum + tonumber(a) end
end
local hist = redis.call('LRANGE', KEYS[2], 0, 49)
local out = {tostring(c5), string.format('%.2f', sum)}
for _, h in ipairs(hist) do out[#out + 1] = h end
return out
"""


@dataclass(frozen=True, slots=True)
class VelocityFeatures:
    tx_count_5m: float
    tx_sum_24h: float
    amount_to_avg_ratio: float

    def as_kwargs(self) -> dict[str, float]:
        return {"tx_count_5m": self.tx_count_5m, "tx_sum_24h": self.tx_sum_24h,
                "amount_to_avg_ratio": self.amount_to_avg_ratio}


NEUTRAL = VelocityFeatures(0.0, 0.0, 1.0)


def window_key(user_id: uuid.UUID | str) -> str:
    return f"vel:{{{user_id}}}"


def history_key(user_id: uuid.UUID | str) -> str:
    return f"hist:{{{user_id}}}"


class VelocityStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._script = redis.register_script(_LUA)
        self._peek_script = redis.register_script(_LUA_PEEK)

    async def observe(self, user_id: uuid.UUID, tx_id: uuid.UUID, amount: float, now_ts: float) -> VelocityFeatures:
        """Return features for this tx (from PRIOR activity) and record it. One round trip."""
        amt = f"{amount:.2f}"
        out = await self._script(
            keys=[window_key(user_id), history_key(user_id)],
            args=[f"{now_ts:.3f}", amt, f"{tx_id}:{amt}"],
        )
        return self._features(out, amount)

    async def peek(self, user_id: uuid.UUID, amount: float, now_ts: float) -> VelocityFeatures:
        """Same features `observe` would return right now, WITHOUT recording anything (live risk preview)."""
        out = await self._peek_script(keys=[window_key(user_id), history_key(user_id)], args=[f"{now_ts:.3f}"])
        return self._features(out, amount)

    @staticmethod
    def _features(out: list[str], amount: float) -> VelocityFeatures:
        count5, sum24 = float(out[0]), float(out[1])
        prior = [float(x) for x in out[2:]]
        med = statistics.median(prior) if len(prior) >= 3 else 0.0
        return VelocityFeatures(count5, sum24, amount / med if med > 0 else 1.0)

    async def clear(self, user_id: uuid.UUID) -> None:
        await self._redis.delete(window_key(user_id), history_key(user_id), f"forecast:{user_id}")
