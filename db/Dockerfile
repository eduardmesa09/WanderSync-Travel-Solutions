FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY migrate.py .
COPY migrations/ migrations/

USER nobody
CMD ["python", "migrate.py"]
