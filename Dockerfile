# =============================================================================
# LeechBot - Dockerfile
# =============================================================================
# Multi-stage build for minimal image size
# Supports: x86_64, ARM64 (Oracle Cloud, Raspberry Pi, Apple Silicon)
# =============================================================================

# Pin Bookworm — `python:3.12-slim` tracks Debian testing (Trixie) where `unrar`
# is not in default repos; Bookworm + non-free keeps Railway/Fly/Render one-click builds working.
FROM python:3.12-slim-bookworm AS base

LABEL maintainer="Shinei Nouzen <https://github.com/Shineii86>" \
      description="Advanced Telegram File Transloader" \
      version="3.1.47"

# Prevent Python from buffering output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies in a single layer
# - ffmpeg: video/audio processing
# - aria2: HTTP/FTP/Bittorrent downloader
# - p7zip-full, unrar, unzip: archive handling
# - python3-libtorrent: magnet/torrent downloads (DHT, resume, progress)
# - curl: health checks
# - tini: proper PID 1 signal handling (SIGTERM → graceful shutdown)
RUN sed -i -E 's/^Components: main$/Components: main contrib non-free non-free-firmware/' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        p7zip-full \
        unrar \
        unzip \
        python3-libtorrent \
        curl \
        tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install megatools — try apt first, fall back to source build
RUN apt-get update && apt-get install -y --no-install-recommends megatools \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    || (curl -fsSL https://github.com/megous/megatools/releases/download/1.11.1/megatools-1.11.1.tar.gz | tar xz \
        && cd megatools-1.11.1 && ./configure && make && make install && cd .. \
        && rm -rf megatools-1.11.1)

# Create app directory
WORKDIR /app

# Copy requirements first (Docker layer caching — deps change less than code)
COPY requirements.txt .
# TgCrypto has no cp312 wheel on some platforms — compile with gcc, then drop build deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Create runtime directories (sessions, downloads, etc. mounted as volumes)
RUN mkdir -p sessions downloads temp work thumbnails logs

# Default port for web dashboard
EXPOSE 8080

# Health check — lightweight HTTP probe, no auth required
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Use tini as PID 1 — forwards signals properly so the bot shuts down cleanly
# Without tini, Python runs as PID 1 and doesn't receive SIGTERM from `docker stop`
ENTRYPOINT ["tini", "--"]

# Run the bot
CMD ["python3", "-m", "leechbot"]
