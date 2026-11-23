#!/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/bash
# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
# Acme Lab CI/CD Suite (Pytest Version)

echo "🔍 Priming components..."
python src/preflight_check.py

echo "🧪 Running Pytest suite..."
python -m pytest src/test_*.py
