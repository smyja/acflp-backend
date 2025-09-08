from arq.connections import RedisSettings

from ...core.config import settings
from .functions import sample_background_task, shutdown, startup

REDIS_QUEUE_HOST = settings.REDIS_QUEUE_HOST
REDIS_QUEUE_PORT = settings.REDIS_QUEUE_PORT
REDIS_QUEUE_PASSWORD = getattr(settings, "REDIS_QUEUE_PASSWORD", None)
REDIS_QUEUE_DB = getattr(settings, "REDIS_QUEUE_DB", 0)


class WorkerSettings:
    functions = [sample_background_task]
    redis_settings = RedisSettings(
        host=REDIS_QUEUE_HOST,
        port=REDIS_QUEUE_PORT,
        password=REDIS_QUEUE_PASSWORD,
        database=REDIS_QUEUE_DB,
    )
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
