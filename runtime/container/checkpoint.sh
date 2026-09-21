#!/usr/bin/env bash
# checkpoint.sh — mark "I believe step <n> is done" WITHOUT submitting.
#
#   ./checkpoint.sh 1      tag the current tree as the step-1 boundary
#   ./checkpoint.sh list   show checkpoints recorded so far
#
# Lives beside submit.sh in the agent image and is symlinked into /workspace.
#
# WHY THIS EXISTS. The benchmark needs seed trees gated "passes t_1..t_N, fails t_{N+1}",
# and an earlier survey found none in git history because frontier models one-shot all three steps in a single
# commit. Some are recoverable from FAILED submissions of multi-attempt rollouts
# (the seed-tree finder finds 25, covering 7 of 22 slots) — but that only yields a
# candidate where a contestant happened to fail at exactly that boundary. The other 15
# slots have none and never will, because a model that succeeds leaves no boundary behind.
#
# This closes the gap structurally: every future rollout leaves candidates whether or not
# the model struggles.
#
# WHAT IT DELIBERATELY DOES NOT DO — and this is the whole design:
#
#   * NO submission. The scoring formula is 100 x Outcome x 0.80^(submissions-1) x ... ,
#     and that 0.80 exists precisely to make probing a losing strategy. Probing is also
#     exactly the behaviour that would produce verified boundary trees. So a checkpoint
#     must not consume k — otherwise we would be asking the agent to damage its own score
#     to give us data, and a rational agent would refuse.
#   * NO grading. It never touches /mailbox/submit, so the runner never sees it and no
#     device time is spent. A checkpoint is a CLAIM, not a verified state: the tree may not
#     pass t_n at all, or may already contain step-(n+1) code. Every candidate is still
#     gated later against the frozen suites before it becomes a scaffold.
#   * NO feedback. Reading a verdict is what submission is for. If a checkpoint returned
#     anything about correctness it would be a free probe, which is the thing the
#     submission economy is built to price.
#
# It writes a git tag and a line in .revyl-checkpoints.json inside the workspace, both of
# which travel with the tree into workspace.bundle at collection.
set -eo pipefail

WS="${BENCH_WORKSPACE:-/workspace}"
LEDGER="$WS/.revyl-checkpoints.json"
cd "$WS" || { echo "checkpoint.sh: no $WS" >&2; exit 1; }

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ "${1:-}" = "list" ]; then
  [ -s "$LEDGER" ] && cat "$LEDGER" || echo "[]"
  exit 0
fi

n="${1:-}"
case "$n" in
  1|2|3) ;;
  *) echo "usage: ./checkpoint.sh <1|2|3> | list" >&2; exit 2;;
esac

# Commit first for the same reason submit.sh does: a tag must name a recorded tree, or the
# hash we store describes something that was never written down.
git add -A >/dev/null 2>&1 || true
if ! git diff --cached --quiet 2>/dev/null; then
  git -c user.name=agent -c user.email=agent@revyl-bench \
      commit -q -m "checkpoint: step $n" --allow-empty
fi

commit=$(git rev-parse HEAD)
tree=$(git rev-parse "HEAD^{tree}")
tag="checkpoint-step-$n"
git tag -f "$tag" >/dev/null 2>&1 || true

python3 - "$LEDGER" "$n" "$commit" "$tree" "$(now)" <<'PY'
import json, os, sys
ledger, n, commit, tree, ts = sys.argv[1:6]
rows = []
if os.path.exists(ledger):
    try: rows = json.load(open(ledger))
    except Exception: rows = []
# keep every claim, including repeats: an agent that checkpoints step 2 twice tells us
# something about where it thought the boundary was, and dropping the earlier one would
# silently discard a candidate tree
rows.append({"step": int(n), "commit": commit, "tree": tree, "ts": ts})
json.dump(rows, open(ledger, "w"), indent=2)
PY

echo "CHECKPOINT step=$n commit=${commit:0:12} tree=${tree:0:12}"
echo "  (not a submission — no grading, no k consumed, no feedback)"
