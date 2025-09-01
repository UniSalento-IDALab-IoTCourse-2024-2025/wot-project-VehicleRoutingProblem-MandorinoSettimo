FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dipendenze di build (ortools di solito non ne ha bisogno, ma teniamo build-essential per sicurezza)
RUN apt-get update && apt-get-y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# healthcheck semplice (se vuoi puoi fare una /health; intanto usiamo /docs)
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs')" >/dev/null 2>&1 || exit 1

# api.api:app -> cartella 'api', file 'api.py', variabile FastAPI 'app'
CMD ["uvicorn", "api.api:app", "--host", "0.0.0.0", "--port", "8000"]
