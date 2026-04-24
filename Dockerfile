FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install system dependencies if required (mostly empty for light apps)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc-dev python3-dev && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Compile the bridge with Cython for maximum performance
RUN python3 setup_cython.py build_ext --inplace && rm fastapi_bridge.py setup_cython.py

# Expose the API port
EXPOSE 8000

# Start server using Gunicorn
# Note: We use the same module name 'fastapi_bridge' which now points to the compiled .so file
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "0", "fastapi_bridge:app"]
