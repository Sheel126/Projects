-- Atomic sliding-window rate limiter (see docs/lessons/00-foundations.md §4).
--
-- KEYS[1]  sorted set holding one member per admitted request, score = admit time (ms)
-- ARGV[1]  window length in ms
-- ARGV[2]  max requests allowed inside any window
-- ARGV[3]  unique member id for this request
--
-- Returns {allowed (1/0), requests_in_window, retry_after_ms}
--
-- Time comes from the Redis server (TIME), not the caller, so several processes
-- with slightly different clocks still agree on what "the last 60 seconds" means.

local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local member = ARGV[3]

local t = redis.call('TIME')
local now_ms = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)

-- 1. Forget requests that have slid out of the window.
redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)

-- 2. Count what is left.
local count = redis.call('ZCARD', key)

if count < limit then
  -- 3. Admit and record.
  redis.call('ZADD', key, now_ms, member)
  -- 4. Idle keys expire on their own.
  redis.call('PEXPIRE', key, window_ms)
  return {1, count + 1, 0}
end

-- Denied: the earliest admitted request tells us when a slot frees up.
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry_after = window_ms
if oldest[2] then
  retry_after = math.max(1, tonumber(oldest[2]) + window_ms - now_ms)
end
return {0, count, retry_after}
