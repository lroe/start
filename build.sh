
#!/bin/bash

# This line makes the script exit immediately if any command fails
set -e

# 1. Install Python Dependencies
echo "--- Installing Python dependencies ---"
pip install -r requirements.txt

# 2. Navigate into the frontend directory and build the React app
echo "--- Building frontend ---"
cd frontend
npm install
npm run build
echo "--- Frontend build complete. ---"