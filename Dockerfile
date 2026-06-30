FROM python:3.12-slim
WORKDIR /app

# Install build dependencies for packages with C extensions (hdbscan, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clean up build dependencies to reduce image size
RUN apt-get purge -y --auto-remove gcc g++ build-essential

COPY . .
# Railway injects PORT; expose both default and dynamic
EXPOSE 8000
# Use shell form to allow environment variable expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
