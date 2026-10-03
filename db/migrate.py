"""Aplica las migraciones SQL de db/migrations/ en orden.

Uso: DATABASE_URL=postgresql://... python migrate.py

Cada archivo se aplica una sola vez, dentro de su propia transacción, y queda
registrado en meta.schema_migrations con su checksum. Si un archivo ya aplicado
cambia, el script se detiene: las migraciones aplicadas no se editan, se agrega
una nueva.
"""

import hashlib
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Número arbitrario para el advisory lock: evita que dos procesos migren a la vez.
LOCK_ID = 7_300_001


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Falta la variable DATABASE_URL", file=sys.stderr)
        return 1

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("select pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            _ensure_table(conn)
            applied = dict(conn.execute("select name, checksum from meta.schema_migrations").fetchall())
            for path in files:
                sql = path.read_text(encoding="utf-8")
                # Se normalizan los finales de línea: git en Windows puede entregar CRLF.
                checksum = hashlib.sha256(sql.replace("\r\n", "\n").encode()).hexdigest()
                if path.name in applied:
                    if applied[path.name] != checksum:
                        print(f"ERROR: {path.name} cambió después de aplicarse. Crea una migración nueva.", file=sys.stderr)
                        return 1
                    continue
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute(
                        "insert into meta.schema_migrations (name, checksum) values (%s, %s)",
                        (path.name, checksum),
                    )
                print(f"aplicada  {path.name}")
        finally:
            conn.execute("select pg_advisory_unlock(%s)", (LOCK_ID,))

    print(f"Base de datos al día ({len(files)} migraciones).")
    return 0


def _ensure_table(conn: psycopg.Connection) -> None:
    conn.execute("create schema if not exists meta")
    conn.execute(
        """
        create table if not exists meta.schema_migrations (
            name       text primary key,
            checksum   text not null,
            applied_at timestamptz not null default now()
        )
        """
    )


if __name__ == "__main__":
    sys.exit(main())
