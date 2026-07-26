# syntax=docker/dockerfile:1

# --------------------------------------------------------------------------- #
# KI Bewerbungs Coach – Web-Demo
# Baut ein schlankes Image, das die interaktive CLI pro Browser-Sitzung in
# einer PTY startet und über einen FastAPI-WebSocket-Server bereitstellt.
# --------------------------------------------------------------------------- #
FROM python:3.12-slim

# Keine .pyc-Dateien, ungepufferte Ausgabe (wichtig fürs Terminal-Streaming).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Zuerst nur die Paketmetadaten kopieren, damit Layer-Caching greift.
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Anwendung inkl. Web-Extra installieren.
RUN pip install --upgrade pip && pip install ".[web]"

# Unprivilegierten Nutzer anlegen und darauf wechseln.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Healthcheck gegen den /healthz-Endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

CMD ["python", "-m", "ki_bewerbungs_coach.web"]
