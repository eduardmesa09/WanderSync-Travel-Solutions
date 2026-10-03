FROM python:3.12-slim

# Prefect guarda su configuración local en PREFECT_HOME; el usuario nobody no
# tiene directorio personal, así que se le da uno escribible.
ENV PYTHONUNBUFFERED=1 \
    PREFECT_HOME=/tmp/prefect
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

USER nobody
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
