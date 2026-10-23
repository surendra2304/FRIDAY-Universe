FROM python:3.11-slim

WORKDIR /app

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    FORGE_ENV=production

# Install runtime dependencies (git, curl for healthchecks, build-essential, nodejs, npm, golang)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    nodejs \
    npm \
    golang-go \
    && npm install -g typescript --no-audit --no-fund \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm

# Implement container security: Create non-root appuser
RUN useradd -m -u 1000 appuser

# Copy dependency specifications first for layer caching
COPY Forge/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY Forge/ /app/
COPY mesh/ /app/mesh/

# Install project package
RUN pip install --no-cache-dir -e .

# Create required operational directories with correct ownership
RUN mkdir -p /app/data /app/workspaces /app/artifacts \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
