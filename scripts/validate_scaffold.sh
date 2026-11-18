#!/usr/bin/env bash
# validate_scaffold.sh — documentation health check for IQ Option Bot.
#
# Run from the repository root:
#   bash scripts/validate_scaffold.sh
#
# Use --staging while the docs still live under docs-driven/. Staging mode
# skips scaffold-artefact checks and ignores scaffold-only files.
#
# Exits 0 when all checks pass, 1 otherwise.

set -u

STAGING=0
for arg in "$@"; do
  case "$arg" in
    --staging|-s) STAGING=1 ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
  esac
done

if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  RESET='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; RESET=''
fi

PASS_COUNT=0
FAIL_COUNT=0
FAILURES=()

pass() {
  printf "${GREEN}[PASS]${RESET} %s\n" "$1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  local message="$1"
  shift
  printf "${RED}[FAIL]${RESET} %s\n" "$message"
  for line in "$@"; do
    printf "       %s\n" "$line"
  done
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILURES+=("$message")
}

if command -v rg >/dev/null 2>&1; then
  SEARCH="rg --no-heading -n"
else
  SEARCH="grep -rn"
fi

ROOT="$(pwd)"
echo "Validating documentation at: $ROOT"
echo "----------------------------------------"

# Collect project markdown files, excluding non-doc directories.
collect_markdown() {
  local extra=()
  if [ "$STAGING" -eq 1 ]; then
    extra=(
      -not -path "./prompt.md"
      -not -path "./extract.md"
      -not -path "./MERGE_BACK.md"
      -not -path "./HOW_TO.md"
    )
  fi

  find . -type f -name "*.md" \
    -not -path "./.git/*" \
    -not -path "./.venv/*" \
    -not -path "./node_modules/*" \
    -not -path "./sources/*" \
    -not -path "./docs-driven/*" \
    -not -path "*/__pycache__/*" \
    -not -path "./profiles/*" \
    "${extra[@]}" \
    2>/dev/null
}

markdown=$(collect_markdown)

# Check 1: no 'Project Name' placeholder outside sources/
if echo "$markdown" | xargs -r grep -l "Project Name" 2>/dev/null | grep -q .; then
  fail "'Project Name' placeholder still present" \
    "$(echo "$markdown" | xargs -r grep -n "Project Name" 2>/dev/null | head -5)"
else
  pass "No 'Project Name' placeholder left in project docs"
fi

# Check 2: no 'YYYY-MM-DD' placeholder outside sources/
if echo "$markdown" | xargs -r grep -l "YYYY-MM-DD" 2>/dev/null | grep -q .; then
  fail "'YYYY-MM-DD' placeholder still present" \
    "$(echo "$markdown" | xargs -r grep -n "YYYY-MM-DD" 2>/dev/null | head -5)"
else
  pass "No 'YYYY-MM-DD' placeholder left"
fi

# Check 3: AGENTS.md has no template placeholders
if [ -f AGENTS.md ]; then
  if grep -q "<!-- One-paragraph" AGENTS.md 2>/dev/null; then
    fail "AGENTS.md still has template HTML-comment placeholders"
  else
    pass "AGENTS.md has no template HTML-comment placeholders"
  fi
else
  fail "AGENTS.md not found at project root"
fi

# Check 4: every doc in system/concepts/data/planning has a Status: label
missing_status=()
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if ! head -5 "$f" 2>/dev/null | grep -qE "^Status:"; then
    missing_status+=("$f")
  fi
done < <(find docs/system docs/concepts docs/data docs/planning -name "*.md" -type f 2>/dev/null)

if [ ${#missing_status[@]} -eq 0 ]; then
  pass "All docs in system/concepts/data/planning have a Status label"
else
  fail "${#missing_status[@]} doc(s) missing Status label" "${missing_status[@]}"
fi

# Check 5: every docs/ file has a 'Last updated' footer
missing_footer=()
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if ! tail -5 "$f" 2>/dev/null | grep -q "Last updated"; then
    missing_footer+=("$f")
  fi
done < <(find docs -name "*.md" -type f 2>/dev/null)

if [ ${#missing_footer[@]} -eq 0 ]; then
  pass "All docs/ files have a 'Last updated' footer"
else
  fail "${#missing_footer[@]} doc(s) missing 'Last updated' footer" "${missing_footer[@]}"
fi

# Check 6: AGENTS.md Section 1 has content
if [ -f AGENTS.md ]; then
  section1=$(awk '/^## 1\. What This System Does/,/^---$/' AGENTS.md | sed '1d;$d' | grep -v '^<!--' | grep -v '^$' | head -1)
  if [ -n "$section1" ]; then
    pass "AGENTS.md Section 1 has content"
  else
    fail "AGENTS.md Section 1 is empty" "Add a one-paragraph description under '## 1. What This System Does'"
  fi
fi

# Check 7: README.md is project-specific
if [ -f README.md ]; then
  if grep -q "Universal Project Kickstart" README.md 2>/dev/null; then
    fail "README.md still contains the universal scaffold template"
  else
    pass "README.md is project-specific"
  fi
else
  fail "README.md not found at project root"
fi

# Check 8: docs/index.md links resolve
if [ -f docs/index.md ]; then
  broken_links=()
  links=$(grep -oE '\]\([^)]+\.md[^)]*\)' docs/index.md | sed -E 's/^\]\(//; s/\)$//; s/#.*$//' | sort -u)
  while IFS= read -r link; do
    [ -z "$link" ] && continue
    case "$link" in
      http*|/*|"") continue ;;
    esac
    resolved=$(cd docs 2>/dev/null && python -c "import os,sys; print(os.path.normpath(os.path.join('.', sys.argv[1])))" "$link" 2>/dev/null)
    if [ -n "$resolved" ] && [ ! -f "docs/$resolved" ]; then
      broken_links+=("$link")
    fi
  done <<< "$links"

  if [ ${#broken_links[@]} -eq 0 ]; then
    pass "All links in docs/index.md resolve to existing files"
  else
    fail "${#broken_links[@]} broken link(s) in docs/index.md" "${broken_links[@]}"
  fi
else
  fail "docs/index.md not found"
fi

# Check 9: AGENTS.md Change Log has project-specific entries
if [ -f AGENTS.md ]; then
  changelog=$(awk '/^## 9\. Change Log/,0' AGENTS.md | grep -E "^\| [0-9]{4}-[0-9]{2}-[0-9]{2}" | grep -v "Initial scaffold created" || true)
  if [ -n "$changelog" ]; then
    pass "AGENTS.md Change Log has project-specific entries"
  else
    fail "AGENTS.md Change Log only has the template entry" "Add at least one real change-log entry"
  fi
fi

# Check 10: no unresolved TODO markers in AGENTS.md
if [ -f AGENTS.md ]; then
  todo_hits=$(grep -n "> \*\*TODO:\*\*" AGENTS.md 2>/dev/null || true)
  if [ -z "$todo_hits" ]; then
    pass "AGENTS.md has no unresolved TODOs"
  else
    fail "AGENTS.md has unresolved TODOs" "$todo_hits"
  fi
fi

# Check 11: scaffold-time artefacts absent (skipped in staging mode)
if [ "$STAGING" -eq 0 ]; then
  leaks=()
  [ -d profiles ] && leaks+=("profiles/ directory")
  [ -f prompt.md ] && leaks+=("prompt.md")
  [ -f extract.md ] && leaks+=("extract.md")
  [ -f MERGE_BACK.md ] && leaks+=("MERGE_BACK.md")
  [ -f HOW_TO.md ] && leaks+=("HOW_TO.md")
  if [ ${#leaks[@]} -eq 0 ]; then
    pass "No scaffold-time artefacts present"
  else
    fail "${#leaks[@]} scaffold-time artefact(s) present" "${leaks[@]}"
  fi
else
  printf "${YELLOW}[SKIP]${RESET} Scaffold-time artefact check (staging mode)\n"
fi

echo "----------------------------------------"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
if [ "$FAIL_COUNT" -eq 0 ]; then
  printf "${GREEN}Summary: %d/%d checks passed. Documentation is clean.${RESET}\n" "$PASS_COUNT" "$TOTAL"
  exit 0
else
  printf "${YELLOW}Summary: %d/%d checks passed. Fix the %d failure(s) and re-run.${RESET}\n" "$PASS_COUNT" "$TOTAL" "$FAIL_COUNT"
  exit 1
fi
