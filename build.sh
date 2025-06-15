#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# 1. Install Python Dependencies in the root directory
echo "--- Installing Python dependencies... ---"
pip install -r requirements.txt

# 2. Build the frontend
echo "--- Building frontend... ---"
# Navigate into the frontend directory, install dependencies, and build the app
# This entire block is executed within the 'frontend' directory
(cd frontend && npm install && npm run build)

echo "--- Build script finished. ---"
