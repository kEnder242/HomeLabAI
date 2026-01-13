#!/bin/bash
# Acme Lab CI/CD Suite (Pytest Version)

echo "🔍 Priming components..."
.venv/bin/python src/preflight_check.py

echo "🧪 Running Pytest suite..."
.venv/bin/pytest src/test_*.py
