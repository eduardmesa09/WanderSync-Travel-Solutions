"""Regenera schema.graphql, el contrato que usa el frontend.

Uso (desde services/gateway): python export_schema.py
Ejecutarlo cada vez que cambie app/schema.py y subir el archivo resultante.
"""

import os
from pathlib import Path

# El esquema no abre conexiones al importarse; solo necesita que la variable exista.
os.environ.setdefault("DATABASE_URL", "postgresql://unused")

from app.schema import schema  # noqa: E402

target = Path(__file__).parent / "schema.graphql"
target.write_text(schema.as_str() + "\n", encoding="utf-8", newline="\n")
print(f"Escrito {target}")
