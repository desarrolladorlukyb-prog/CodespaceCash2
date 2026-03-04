#!/bin/bash
set -e
echo "=== Setting up CodespaceCash2 ==="

cd /workspaces/CodespaceCash2
git pull origin main

# Install Python dependencies
pip install playwright requests 2>&1

# Install Playwright browsers (chromium only)
playwright install chromium 2>&1
playwright install-deps chromium 2>&1

# Create symlinks in home dir so scripts can be called as ~/scrape_*.py
ln -sf /workspaces/CodespaceCash2/scrape_dian.py ~/scrape_dian.py
ln -sf /workspaces/CodespaceCash2/scrape_rama_judicial.py ~/scrape_rama_judicial.py

echo "=== Setup complete ==="
echo "Test with: python ~/scrape_dian.py 123456789"