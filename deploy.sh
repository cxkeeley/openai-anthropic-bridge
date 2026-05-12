#!/bin/bash

# Exit on any error
set -e

echo "🔨 Compiling FastAPI Bridge with Cython..."
python3 setup_cython.py build_ext --inplace

# Cleanup intermediate files
echo "🧹 Cleaning up intermediate build files..."
rm -rf build/
find . -name "*.c" -delete

echo "🚀 Starting Docker Compose deployment..."
docker compose up -d --build

echo "✅ Deployment complete! Bridge is running."
