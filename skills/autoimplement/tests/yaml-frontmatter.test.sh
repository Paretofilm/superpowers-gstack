#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_FILE="$SCRIPT_DIR/../SKILL.md"
[ -f "$SKILL_FILE" ] || { echo "FAIL: SKILL.md not found"; exit 1; }
frontmatter=$(awk 'BEGIN{c=0} /^---$/{c++; next} c==1{print}' "$SKILL_FILE")
[ -n "$frontmatter" ] || { echo "FAIL: no frontmatter"; exit 1; }
echo "$frontmatter" | python3 -c '
import sys, yaml
data = yaml.safe_load(sys.stdin.read())
assert isinstance(data, dict), "FAIL: frontmatter not a mapping"
assert "name" in data, "FAIL: missing name"
name = data["name"]
assert name == "autoimplement", f"FAIL: name is {name!r}"
assert "description" in data, "FAIL: missing description"
assert len(data["description"]) >= 80, f"FAIL: description too short"
print("OK: frontmatter valid")
'
