#!/usr/bin/env bash
# Quality Gates - Run all 7 checks before committing
# Usage: ./run-quality-gates.sh

set -e  # Exit on first failure

echo "🔍 Running Quality Gates (7/7)..."
echo ""

# Check 1: Black formatting
echo "1️⃣  Black formatting..."
black --check execution/domain execution/dashboards/components execution/collectors tests/
echo "   ✅ Black passed"
echo ""

# Check 2: Ruff linting
echo "2️⃣  Ruff linting..."
ruff check execution/ tests/
echo "   ✅ Ruff passed"
echo ""

# Check 3: Type hints (MyPy)
echo "3️⃣  Type hints (MyPy)..."
mypy execution/ tests/
echo "   ✅ MyPy passed"
echo ""

# Check 4: Unit tests (pytest)
echo "4️⃣  Unit tests (pytest)..."
pytest tests/ -v
echo "   ✅ Pytest passed"
echo ""

# Check 5: Security scan (Bandit)
echo "5️⃣  Security scan (Bandit)..."
bandit -r execution/ -ll
echo "   ✅ Bandit passed"
echo ""

# Check 6: Documentation build (Sphinx)
echo "6️⃣  Documentation build (Sphinx)..."
export PYTHONPATH=".:${PYTHONPATH}"
cd docs && sphinx-build -b html . _build/html && cd ..
echo "   ✅ Sphinx passed"
echo ""

# Check 7: Template Security
echo "7️⃣  Template Security..."
grep -q 'autoescape=select_autoescape' execution/template_engine.py || { echo "   ❌ FAIL: Autoescape not configured"; exit 1; }
grep -r "autoescape false" templates/ && { echo "   ❌ FAIL: Found disabled autoescape"; exit 1; } || true
echo "   ✅ Template security passed"
echo ""

echo "🎉 All 7 quality gates PASSED! Safe to commit."
