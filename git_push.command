#!/bin/bash
cd "/Users/zlexxthaitablist/Claude/Projects/MARKETING PLAN"
rm -f .git/HEAD.lock .git/index.lock
git add -A
git diff --cached --quiet || git commit -m "Auto-commit pending changes"
git push origin main
echo ""
echo "=== Done! Press any key to close ==="
read -n1
