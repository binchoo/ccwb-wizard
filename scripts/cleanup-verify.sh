#!/usr/bin/env bash
# cleanup-verify.sh — DEPRECATED.
#
# This script verified the Cleanup unit's commits at the moment they were
# created (HEAD~2 == "Extract" commit). Once subsequent units (Build-Tooling
# in particular) add new commits, the HEAD~2 baseline assumption no longer
# holds and the byte-level checks will produce false negatives.
#
# The Cleanup unit's outcome is now permanent in git history. Re-running
# this verification has no value. The script is left here for archaeology
# only and exits with a clear DEPRECATED notice.
#
# Refs:
#   - aidlc-docs/construction/cleanup/code/summary.md
#   - aidlc-docs/construction/cleanup/code/test-debt-note.md
#   - aidlc-docs/construction/build-tooling/functional-design/business-logic-model.md (Commit 5)

cat <<'EOF'
⚠️  cleanup-verify.sh is DEPRECATED after the Build-Tooling unit.

   This script's HEAD~2 baseline assumption only held immediately after
   the Cleanup unit's commits. Subsequent units have advanced HEAD, and
   re-running this verification is no longer meaningful.

   The Cleanup unit's outcome is permanent in git history; nothing to
   verify here at runtime. See:
     - aidlc-docs/construction/cleanup/code/summary.md
     - aidlc-docs/construction/cleanup/code/test-debt-note.md

   Exiting 0 (no-op).
EOF

exit 0
