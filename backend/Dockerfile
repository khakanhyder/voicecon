FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# MySQL client libs (replacing postgresql)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /app/uploads is created here, not just at runtime: when a volume is mounted
# onto a path that does not exist in the image, Docker creates it owned by root
# and the unprivileged process cannot write an avatar into it. Mounting onto an
# existing appuser-owned directory copies that ownership to the volume.
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/recordings /app/uploads && \
    chown appuser:appuser /app/recordings /app/uploads && \
    chmod +x /app/start.sh

USER appuser

CMD ["/app/start.sh"]
