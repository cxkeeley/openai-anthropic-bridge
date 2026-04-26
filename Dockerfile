FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install system dependencies if required (mostly empty for light apps)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and compiled binary
COPY . .

# Remove the simple source file to ensure Python loads the complex compiled .so binary
RUN rm fastapi_bridge.py

# Expose the API port
EXPOSE 8000

# Start server using Gunicorn for production-level parallel WSGI streaming
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "0", "fastapi_bridge:app"]
