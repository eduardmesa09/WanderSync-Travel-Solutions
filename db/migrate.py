"""Aplica las migraciones SQL de db/migrations/ en orden.

Uso: DATABASE_URL=postgresql://... python migrate.py

Cada archivo se aplica una sola vez y queda registrado en meta.schema_migrations
con su checksum. Todas las pendientes van en una sola transacción: si una falla,
no se aplica ninguna. Si un archivo ya aplicado cambia, el script se detiene:
las migraciones aplicadas no se editan, se agrega una nueva.
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
    try:
        # Sin sentencias preparadas y con un candado de transacción (no de sesión):
        # ambos son requisitos del transaction pooler de Supabase.
        with psycopg.connect(dsn, prepare_threshold=None) as conn, conn.transaction():
            conn.execute("select pg_advisory_xact_lock(%s)", (LOCK_ID,))
            _ensure_table(conn)
            applied = dict(conn.execute("select name, checksum from meta.schema_migrations").fetchall())
            for path in files:
                sql = path.read_text(encoding="utf-8")
                # Se normalizan los finales de línea: git en Windows puede entregar CRLF.
                checksum = hashlib.sha256(sql.replace("\r\n", "\n").encode()).hexdigest()
                if path.name in applied:
                    if applied[path.name] != checksum:
                        raise ChangedMigrationError(path.name)
                    continue
                conn.execute(sql)
                conn.execute(
                    "insert into meta.schema_migrations (name, checksum) values (%s, %s)",
                    (path.name, checksum),
                )
                print(f"aplicada  {path.name}")
    except ChangedMigrationError as error:
        print(f"ERROR: {error} cambió después de aplicarse. Crea una migración nueva.", file=sys.stderr)
        return 1

    print(f"Base de datos al día ({len(files)} migraciones).")
    return 0


class ChangedMigrationError(Exception):
    """Una migración ya aplicada fue modificada."""


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
