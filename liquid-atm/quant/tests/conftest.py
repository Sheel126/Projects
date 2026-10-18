import fakeredis
import pytest


@pytest.fixture
def redis_client():
    # fakeredis[lua] runs our real Lua scripts, so atomicity logic is exercised as written.
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()
