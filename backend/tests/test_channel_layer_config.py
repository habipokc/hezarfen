from channels_redis.core import RedisChannelLayer

# the module itself: the autouse in-memory fixture overrides django.conf.settings
from hezarfen import settings as project_settings


def test_redis_read_timeout_outlasts_the_blocking_receive():
    # An idle consumer blocks in BZPOPMIN for brpop_timeout seconds; if the client-side
    # socket timeout is not longer, every quiet connection dies with TimeoutError.
    layer = RedisChannelLayer(**project_settings.CHANNEL_LAYERS["default"]["CONFIG"])
    assert layer.hosts[0]["socket_timeout"] > layer.brpop_timeout
