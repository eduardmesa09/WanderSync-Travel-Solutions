import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# DATABASE_URL apunta al transaction pooler de Supabase (puerto 6543), que
# reparte muchas conexiones de clientes sobre pocas conexiones reales. En ese
# modo cada transacción puede caer en una conexión distinta, así que no se
# pueden usar sentencias preparadas: prepare_threshold=None las desactiva.
#
# autocommit=True: cada sentencia se confirma sola. Los servicios solo ejecutan
# sentencias independientes, y así cada una cuesta un viaje a Supabase en lugar
# de tres (BEGIN, sentencia, COMMIT). Si algún día hace falta agrupar varias,
# usar `async with conn.transaction():`.
pool = AsyncConnectionPool(
    os.environ["DATABASE_URL"],
    min_size=1,
    max_size=4,
    open=False,
    kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": True},
)
