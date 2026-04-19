import os
import aiomysql

_pool = None

async def mysql_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host      = os.getenv("MYSQL_HOST",     "localhost"),
            port      = int(os.getenv("MYSQL_PORT", "3306")),
            user      = os.getenv("MYSQL_USER",     "root"),
            password  = os.getenv("MYSQL_PASSWORD", "graphrec123"),
            db        = os.getenv("MYSQL_DB",       "graphrec_db"),
            charset   = "utf8mb4",
            autocommit = True,
            minsize   = 2,
            maxsize   = 10,
        )
    return _pool
