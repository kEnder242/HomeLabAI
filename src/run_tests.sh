#!/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/bash
# Acme Lab CI/CD Suite (Pytest Version)

echo "🔍 Priming components..."
python src/preflight_check.py

echo "🧪 Running Pytest suite..."
python -m pytest src/test_*.py
