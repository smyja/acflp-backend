from redis.asyncio import ConnectionPool, Redis

pool: ConnectionPool | None = None
client: Redis | None = None
