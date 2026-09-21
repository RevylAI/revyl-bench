#!/usr/bin/env bash
# submit.sh — the agent's ONLY channel to the grader. Lives at
# /opt/bench/submit.sh in the agent image and is symlinked to /workspace/submit.sh.
#
#   ./submit.sh            commit the working tree, package it, drop it in the mailbox,
#                          print "SUBMITTED k=<k>" and RETURN IMMEDIATELY.
#   ./submit.sh wait <k>   poll the runner's status for up to ~5 min, print progress lines,
#                          and when the verdict lands print the vector + feedback path.
#                          exit 0 = all four PASS, 1 = some FAIL / rejected, 2 = still
#                          pending (call again). Bounded at 5 min because Claude Code's Bash
#                          tool kills any call at 10 min — a blocking 30-min wait would die
#                          mid-poll every single time.
#   ./submit.sh status     last k, its status, submissions used / max.
#
# What this script deliberately CANNOT do: build, upload, run tests, or see the grading
# org — it only writes files into /mailbox/submit and reads /mailbox/feedback (mounted
# read-only). The runner on the other side of the mailbox holds the credentials.
#
# Design notes for the reader:
#  * commit-before-package: the graded binary must correspond to a
#    recorded tree. `git archive HEAD` guarantees the tarball == the commit; an uncommitted
#    edit can't ship. --allow-empty so a retry after a tooling failure re-grades the same
#    tree with a new k.
#  * write tmp → rename: the runner watches for `s<k>.request.json`; the tarball is fully
#    written and its sha256 recorded before the request file appears (atomic rename).
#  * k is derived from the mailbox (max existing request + 1), not from a counter the agent
#    could edit; the runner re-validates the sequence anyway (rejected: sequence).
set -eo pipefail

MAILBOX="${BENCH_MAILBOX:-/mailbox}"
WS="${BENCH_WORKSPACE:-/workspace}"
SUBMIT="$MAILBOX/submit"
FEEDBACK="$MAILBOX/feedback"
INFRA="$WS/infra_runtime.json"

die() { echo "submit.sh: $*" >&2; exit 1; }

next_k() {
  local max=0 f n
  for f in "$SUBMIT"/s*.request.json; do
    [ -e "$f" ] || continue
    n=$(basename "$f" | sed -E 's/^s([0-9]+)\.request\.json$/\1/')
    [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -gt "$max" ] && max=$n
  done
  echo $((max + 1))
}

last_k() { local k; k=$(next_k); echo $((k - 1)); }

# Native tasks only (infra_runtime.json require_dev_build): the tree about to be submitted
# must be one that a development build has already compiled — a submission of an unbuilt
# tree fails to build on the grader and still costs one of the few submissions. The index
# is staged (git add -A) before this runs, so `git write-tree` is exactly the tree that
# `git archive HEAD` would ship; it must equal the tree of a READY build in .devbuilds/.
require_dev_build() {
  [ "$(jq -r '.require_dev_build // false' "$INFRA" 2>/dev/null)" = "true" ] || return 0
  local state="$WS/.devbuilds" tree f c
  # Compared over the paths that reach the grader's build. Left out: infra_runtime.json
  # (both shims bump its counters after committing), .revyl-checkpoints.json (written by
  # checkpoint.sh) and .revyl/ (revyl dev writes device-sessions.json and dev-sessions/
  # there, and the grader overwrites config.yaml with its own recipe anyway).
  tree_key() { git ls-tree -r "$1" | grep -vE $'\t(infra_runtime\.json|\.revyl-checkpoints\.json|\.revyl/.*)$' | sha256sum | cut -d' ' -f1; }
  tree=$(tree_key "$(git write-tree)")
  for f in "$state"/b*.json; do
    [ -e "$f" ] || continue
    [ "$(jq -r '.status // ""' "$f")" = "ready" ] || continue
    c=$(jq -r '.commit // ""' "$f"); [ -n "$c" ] || continue
    git rev-parse --verify -q "$c^{tree}" >/dev/null || continue
    [ "$(tree_key "$c^{tree}")" = "$tree" ] && return 0
  done
  die "this tree has no READY development build — run ./devbuild.sh, then ./devbuild.sh wait <k>, and submit the tree that built (an unbuilt tree fails to build on the grader and still spends a submission)"
}

cmd_submit() {
  cd "$WS" || die "no workspace at $WS"
  [ -d .git ] || die "$WS is not a git repo"
  local max_sub used k
  max_sub=$(jq -r '.max_submissions // 5' "$INFRA" 2>/dev/null || echo 5)
  k=$(next_k)
  # Reject locally when the previous submission is still in flight — the runner would
  # reject too (rejected: in_flight), this just gives a clearer message and no wasted commit.
  if [ "$k" -gt 1 ] && [ ! -e "$FEEDBACK/s$((k-1)).verdict.json" ] && \
     ! grep -qE '^rejected' "$FEEDBACK/s$((k-1)).status" 2>/dev/null; then
    die "submission $((k-1)) is still being graded — run: ./submit.sh wait $((k-1))"
  fi
  if [ "$k" -gt "$max_sub" ]; then
    die "submission cap reached ($max_sub). No further submissions will be graded."
  fi

  git add -A
  require_dev_build
  git -c user.name="agent" -c user.email="agent@revyl-bench" \
      commit -q --allow-empty -m "submission $k" || die "git commit failed"
  local commit sha tmp tar
  commit=$(git rev-parse HEAD)
  tmp="$SUBMIT/.s$k.tar.gz.tmp"
  tar="$SUBMIT/s$k.tar.gz"
  git archive --format=tar.gz -o "$tmp" HEAD || die "git archive failed"
  sha=$(sha256sum "$tmp" | cut -d' ' -f1)
  mv -f "$tmp" "$tar"
  # request.json LAST — its appearance is the runner's trigger; by then the tarball is complete.
  jq -n --arg rid "$(jq -r .rollout_id "$INFRA")" --argjson k "$k" --arg c "$commit" \
        --arg s "$sha" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '{rollout_id:$rid,k:$k,commit_id:$c,sha256:$s,ts:$ts}' > "$SUBMIT/.s$k.request.tmp"
  mv -f "$SUBMIT/.s$k.request.tmp" "$SUBMIT/s$k.request.json"
  # UX counter only — the runner is authoritative.
  used=$(jq -r '.submissions_used // 0' "$INFRA"); used=$((used + 1))
  jq --argjson u "$used" '.submissions_used=$u' "$INFRA" > "$INFRA.tmp" && mv -f "$INFRA.tmp" "$INFRA"
  echo "SUBMITTED k=$k commit=$commit sha256=${sha:0:12} ($used/$max_sub submissions used)"
  echo "Grading takes ~20-35 min (cloud build + device suite). Poll with: ./submit.sh wait $k"
}

print_verdict() {
  local k="$1" v="$FEEDBACK/s$k.verdict.json"
  local t1 t2 t3 fin regs
  t1=$(jq -r '.verdicts.t_1' "$v"); t2=$(jq -r '.verdicts.t_2' "$v")
  t3=$(jq -r '.verdicts.t_3' "$v"); fin=$(jq -r '.verdicts.final' "$v")
  regs=$(jq -r '.regressions | join(",")' "$v")
  echo "VERDICT k=$k  t_1=$t1  t_2=$t2  t_3=$t3  final=$fin  regressions=[${regs}]"
  local fk; fk=$(jq -r '.failure_kind // empty' "$v")
  [ -n "$fk" ] && echo "NOTE: failure_kind=$fk (tooling; see feedback for details)"
  local lw; lw=$(jq -r '.lint_warnings | length' "$v")
  [ "$lw" != "0" ] && echo "lint_warnings: $(jq -c '.lint_warnings' "$v")"
  if [ -d "$FEEDBACK/s$k" ]; then
    echo "Feedback bundle: $FEEDBACK/s$k/  (failed_criteria.json, screenshots/, launch_errors.txt if any)"
    local n; n=$(jq 'length' "$FEEDBACK/s$k/failed_criteria.json" 2>/dev/null || echo 0)
    echo "  $n failed criteria. Read $FEEDBACK/s$k/failed_criteria.json first."
  fi
  if [ "$t1$t2$t3$fin" = "PASSPASSPASSPASS" ]; then return 0; else return 1; fi
}

cmd_wait() {
  local k="${1:-$(last_k)}"
  [ "$k" -ge 1 ] 2>/dev/null || die "no submission yet"
  local deadline=$(( $(date +%s) + 300 )) st
  while :; do
    if [ -e "$FEEDBACK/s$k.verdict.json" ]; then print_verdict "$k"; return $?; fi
    st=$(cat "$FEEDBACK/s$k.status" 2>/dev/null || echo "queued")
    case "$st" in
      rejected*) echo "REJECTED k=$k: $st"; return 1 ;;
    esac
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "PENDING k=$k status=$st — still grading; call './submit.sh wait $k' again."
      return 2
    fi
    echo "$(date -u +%H:%M:%S) k=$k status=$st"
    sleep 20
  done
}

cmd_status() {
  local k; k=$(last_k)
  local max_sub used
  max_sub=$(jq -r '.max_submissions // 5' "$INFRA"); used=$(jq -r '.submissions_used // 0' "$INFRA")
  if [ "$k" -lt 1 ]; then echo "no submissions yet ($used/$max_sub used)"; return 0; fi
  if [ -e "$FEEDBACK/s$k.verdict.json" ]; then print_verdict "$k" || true
  else echo "k=$k status=$(cat "$FEEDBACK/s$k.status" 2>/dev/null || echo queued)"; fi
  echo "submissions used: $used/$max_sub"
  [ -e "$FEEDBACK/END.json" ] && echo "ROLLOUT ENDED: $(cat "$FEEDBACK/END.json")"
  return 0
}

case "${1:-submit}" in
  submit|"") cmd_submit ;;
  wait)      cmd_wait "${2:-}" ;;
  status)    cmd_status ;;
  *)         die "usage: ./submit.sh [submit|wait <k>|status]" ;;
esac
