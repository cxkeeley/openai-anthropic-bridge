FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the compiled binary and necessary files (.dockerignore handles the rest)
COPY . .

# Expose the API port
EXPOSE 8000

# Start server using Gunicorn
# Note: We use the same module name 'fastapi_bridge' which now points to the compiled .so file
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "0", "fastapi_bridge:app"]
