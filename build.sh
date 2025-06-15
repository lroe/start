#!/usr/bin/env bash
# Exit on error
set -e

# 1. Install Python Dependencies
pip install -r requirements.txt

# 2. Build Frontend
# The $RENDER_SRC_ROOT variable is an absolute path to your project root
cd $RENDER_SRC_ROOT/frontend
npm install
npm run build
