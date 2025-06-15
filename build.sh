#!/usr/bin/env bash
# This script will exit immediately if any command fails, which is good for debugging.
set -e

echo "--- Starting build process... ---"

# 1. Install Python Dependencies in the root directory first.
echo "--- Installing Python dependencies... ---"
pip install -r requirements.txt

# 2. Build the frontend.
echo "--- Building frontend... ---"

# This is the most important part.
# We explicitly change directory to the 'frontend' folder before running npm.
# This guarantees that 'npm install' finds the 'package.json'.
cd frontend

echo "--- Running 'npm install'... (Current directory: $(pwd)) ---"
npm install

echo "--- Running 'npm run build'... ---"
npm run build

echo "--- Build script finished successfully! ---"
