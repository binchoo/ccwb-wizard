#!/usr/bin/env bash
# cleanup-verify.sh — verify the Cleanup unit's 5 commits.
#
# Idempotent, read-only. No auto-rollback (Q3=A).
# Pattern refs: aidlc-docs/construction/cleanup/nfr-design/nfr-design-patterns.md
#
# Steps:
#   STEP A: 4 web/ directories present
#   STEP B: web/domain/ccwb_domain/bedrock_models.py compiles
#   STEP C: 3 credential_provider files match baseline (HEAD~2 = pre-move)
#   STEP D: legacy directories/files absent, source/pyproject.toml present
#
# Exit codes:
#   0 — all 4 STEPs passed
#   1 — at least one verification check failed
#   2 — precondition violation (missing tool, dirty git tree, etc.)

set -u
set -o pipefail

# --- Helpers ---------------------------------------------------------------

# OS-aware sha256 of a file path.
compute_sha256() {
    local file="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$file" | awk '{print $1}'
    else
        echo "ERROR: neither sha256sum nor shasum is available" >&2
        return 2
    fi
}

# OS-aware sha256 of stdin.
compute_sha256_stdin() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 | awk '{print $1}'
    else
        echo "ERROR: neither sha256sum nor shasum is available" >&2
        return 2
    fi
}

# Baseline sha256 from HEAD~2 (pre-move state, i.e. commit 2 — Extract).
extract_baseline_sha() {
    local file_basename="$1"
    git show HEAD~2:source/credential_provider/"$file_basename" 2>/dev/null \
        | compute_sha256_stdin
}

failures=()

record_fail() {
    failures+=("$1")
}

# --- Precondition checks ---------------------------------------------------

if ! command -v git >/dev/null 2>&1; then
    echo "❌ Precondition: git not found." >&2
    exit 2
fi

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Precondition: python/python3 not found." >&2
    exit 2
fi
PY_BIN=$(command -v python || command -v python3)

# --- STEP A: directory presence -------------------------------------------

for dir in web/domain web/backend web/frontend web/binaries; do
    if [[ ! -d "$dir" ]]; then
        record_fail "STEP A: missing directory $dir"
    fi
done

# --- STEP B: bedrock_models.py compiles -----------------------------------

target="web/domain/ccwb_domain/bedrock_models.py"
if [[ ! -f "$target" ]]; then
    record_fail "STEP B: missing file $target"
elif ! "$PY_BIN" -m py_compile "$target" >/dev/null 2>&1; then
    record_fail "STEP B: $target failed py_compile"
fi

# --- STEP C: credential_provider sha256 vs baseline -----------------------

for f in __init__.py __main__.py bedrock_metadata.py; do
    target_file="web/binaries/credential_provider/$f"
    if [[ ! -f "$target_file" ]]; then
        record_fail "STEP C: missing $target_file"
        continue
    fi
    actual=$(compute_sha256 "$target_file")
    baseline=$(extract_baseline_sha "$f")
    if [[ -z "$baseline" ]]; then
        record_fail "STEP C: cannot read baseline for $f from HEAD~2 (history may differ from expected commit layout)"
        continue
    fi
    if [[ "$actual" != "$baseline" ]]; then
        record_fail "STEP C: sha256 mismatch for $target_file (expected $baseline, got $actual)"
    fi
done

# --- STEP D: legacy absence (in git tracking) + pyproject.toml presence ---
# We check git ls-files rather than filesystem `[[ -e ... ]]` because Python
# leaves __pycache__ directories behind which are not tracked by git. The
# Cleanup unit's responsibility is the git history, not local filesystem
# debris (which Build-Tooling will handle via .gitignore).

for absent in source/claude_code_with_bedrock source/credential_provider source/tests; do
    if git ls-files --error-unmatch "$absent" >/dev/null 2>&1 \
        || git ls-files "$absent" 2>/dev/null | grep -q .; then
        record_fail "STEP D: legacy path still tracked by git: $absent"
    fi
done

if git ls-files --error-unmatch source/poetry.lock >/dev/null 2>&1; then
    record_fail "STEP D: source/poetry.lock still tracked by git"
fi

if [[ ! -f source/pyproject.toml ]] || ! git ls-files --error-unmatch source/pyproject.toml >/dev/null 2>&1; then
    record_fail "STEP D: source/pyproject.toml missing or untracked (Build-Tooling unit will migrate it; should still exist now)"
fi

# --- Report ----------------------------------------------------------------

if [[ ${#failures[@]} -eq 0 ]]; then
    echo "✓ Cleanup verification: 4/4 checks passed."
    exit 0
fi

for msg in "${failures[@]}"; do
    echo "❌ Verification failed: $msg"
done
echo ""
echo "Run 'git revert HEAD~4..HEAD' to undo the 5 cleanup commits (chore + 4 feat)."
exit 1
