# Servidor de Prefect. La imagen oficial 3.8.7 trae SQLAlchemy 2.1, con la que
# su programador falla al crear las corridas automáticas ("Can't evaluate bulk
# DML statement") y los horarios nunca se ejecutan. Se fija la última 2.0.
FROM prefecthq/prefect:3.8.7-python3.12

RUN pip install --no-cache-dir "sqlalchemy[asyncio]==2.0.54"
