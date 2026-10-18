-- Atomic counting semaphore with leases (used to cap concurrent GPU inference).
--
-- KEYS[1]  sorted set of current holders, score = lease expiry (ms)
-- ARGV[1]  max concurrent holders
-- ARGV[2]  lease length in ms (a crashed holder frees its slot after this)
-- ARGV[3]  holder token
--
-- Returns 1 if acquired, 0 otherwise.

local key = KEYS[1]
local limit = tonumber(ARGV[1])
local lease_ms = tonumber(ARGV[2])
local token = ARGV[3]

local t = redis.call('TIME')
local now_ms = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)

-- Evict holders whose lease expired (the process died without releasing).
redis.call('ZREMRANGEBYSCORE', key, 0, now_ms)

if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now_ms + lease_ms, token)
  redis.call('PEXPIRE', key, lease_ms)
  return 1
end
return 0
