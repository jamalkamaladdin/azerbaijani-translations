#!/usr/bin/env bash
# Refresh the list from GitHub and publish it. Run this after a translation PR is merged.
set -euo pipefail
B=$(dirname "$(readlink -f "$0")")
python3 "$B/update.py"
cd "$B/.."
git add -A
if git diff --cached --quiet; then echo "deyisiklik yoxdur"; exit 0; fi
git commit -q -m "chore: refresh the merged translation list"
git push -q
echo "siyahi yenilendi ve gonderildi"
