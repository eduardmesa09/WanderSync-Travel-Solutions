import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Pool pequeño: el session pooler de Supabase admite pocas conexiones en total
# y lo comparten todos los microservicios.
pool = AsyncConnectionPool(
    os.environ["DATABASE_URL"],
    min_size=1,
    max_size=2,
    open=False,
    kwargs={"row_factory": dict_row},
)
