FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY . .

# Create artifacts and persistent data directories
RUN mkdir -p artifacts /data

# Railway injects PORT env var
ENV PORT=8000
EXPOSE 8000

# Run the API - use shell form to expand $PORT
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
