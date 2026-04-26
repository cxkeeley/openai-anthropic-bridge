#!/bin/bash

# Exit on any error
set -e

echo "🔨 Compiling FastAPI Bridge with Cython..."
python3 setup_cython.py build_ext --inplace

echo "🚀 Starting Docker Compose deployment..."
docker compose up -d --build

echo "✅ Deployment complete! Bridge is running."
