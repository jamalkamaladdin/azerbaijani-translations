#!/usr/bin/env bash
# Refresh the list from GitHub and publish it. Run this after a translation PR is merged.
# Star counts move every hour, so a run that only shifts stars is dropped instead of
# committed. A changed word count does count as real content and is committed.
# Numbers are still refreshed once the last commit is older than STALE_DAYS.
set -euo pipefail
STALE_DAYS=7
B=$(dirname "$(readlink -f "$0")")
R="$B/.."
J="$R/data/translations.json"
OWNED=(README.md data/translations.json)

keys() { python3 -c "
import json,sys
try: rows = json.load(open(sys.argv[1]))
except Exception: rows = []
print('\n'.join(sorted('%s %s %s' % (r['url'], r.get('merged_at',''), r.get('words','')) for r in rows)))" "$1"; }

before=$(keys "$J")
python3 "$B/update.py"
after=$(keys "$J")

cd "$R"
if git diff --quiet -- "${OWNED[@]}" && git diff --cached --quiet -- "${OWNED[@]}"; then
  echo "deyisiklik yoxdur"; exit 0
fi

last=$(git log -1 --format=%ct 2>/dev/null || echo 0)
age=$(( ($(date +%s) - last) / 86400 ))
if [ "$before" = "$after" ] && [ "$age" -lt "$STALE_DAYS" ]; then
  git checkout -- "${OWNED[@]}"
  echo "yeni merge yoxdur, yalniz ulduz sayi deyisib, commit edilmedi"
  exit 0
fi

git add -- "${OWNED[@]}"
git commit -q -m "chore: refresh the merged translation list"
git push -q
echo "siyahi yenilendi ve gonderildi"
