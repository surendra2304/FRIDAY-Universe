FROM python:3.11-slim

LABEL maintainer="FRIDAY Universe"
LABEL description="FRIDAY Universe — Unified Multi-Agent Intelligence Platform v3.0"
LABEL version="3.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/FRIDAY-Universe

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.32.1 \
    httpx==0.27.2 \
    pydantic==2.10.3 \
    pytest==8.3.3 \
    requests==2.32.3 \
    numpy==1.26.4 \
    scipy==1.14.1 \
    matplotlib==3.9.2 \
    pandas==2.2.3

# Copy repository
COPY . /app/FRIDAY-Universe/

# Set PYTHONPATH for all agent modules
ENV PYTHONPATH=/app/FRIDAY-Universe/FRIDAY/apps/core/src:/app/FRIDAY-Universe/Inference/app:/app/FRIDAY-Universe/Inference:/app/FRIDAY-Universe/Memora:/app/FRIDAY-Universe/Stratex:/app/FRIDAY-Universe/Forge/app/services:/app/FRIDAY-Universe/Sentinel/app/services:/app/FRIDAY-Universe/IntelX/intelx/services:/app/FRIDAY-Universe/Futuris/futuris/core:/app/FRIDAY-Universe/VyralX/app/services

# Create data directories
RUN mkdir -p /app/FRIDAY-Universe/FRIDAY/.data/api_server

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# Run API server
EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "friday_core.real_api_server:app", "--host", "0.0.0.0", "--port", "8000"]
