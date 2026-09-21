#!/usr/bin/env bash
# devbuild.sh — the native (Swift) agent's development-build loop. Lives at
# /opt/bench/devbuild.sh in the agent image and is symlinked to /workspace/devbuild.sh.
# Expo tasks never use it: they hot-reload into a pinned dev-client (RUNBOOK.md.tmpl).
#
#   ./devbuild.sh            commit the working tree, queue a Debug simulator build of it on
#                            Revyl's runner (the agent org's dev app), print
#                            "BUILD k=<k> job=<job>" and RETURN IMMEDIATELY.
#   ./devbuild.sh wait <k>   poll the job for up to ~5 min; print READY <version-id> (exit 0),
#                            FAILED with the compiler excerpt (exit 1), or PENDING (exit 2:
#                            call again). Bounded at 5 min for the same reason as submit.sh.
#   ./devbuild.sh status     builds used / max, the last k and its state.
#
# The budget (max_dev_builds in infra_runtime.json) is counted here, in .devbuilds/, and
# audited by the runner from the dev app's version list: version names are
# <rollout_id>-dev<k>, so any other name on the dev app is a build the agent made outside
# this script (a RUNBOOK violation). The recipe is the seed's .revyl/config.yaml
# `development` profile, rendered by launch_rollout from the bench's own Swift template with
# this rollout's dev app id; the agent's edits to that file are irrelevant to grading (the
# grader overwrites it) but would change what THIS script builds, so it is restored first
# from .devbuilds/recipe.yaml.
set -eo pipefail

WS="${BENCH_WORKSPACE:-/workspace}"
INFRA="$WS/infra_runtime.json"
STATE="$WS/.devbuilds"          # gitignored by seed.sh, like submit.sh
SEED_CFG="$STATE/recipe.yaml"      # installed by seed.sh from launch_rollout's render

die() { echo "devbuild.sh: $*" >&2; exit 1; }

next_k() {
  local max=0 f n
  for f in "$STATE"/b*.json; do
    [ -e "$f" ] || continue
    n=$(basename "$f" | sed -E 's/^b([0-9]+)\.json$/\1/')
    [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -gt "$max" ] && max=$n
  done
  echo $((max + 1))
}

cmd_build() {
  cd "$WS" || die "no workspace at $WS"
  [ -d .git ] || die "$WS is not a git repo"
  mkdir -p "$STATE"
  local max k rid
  max=$(jq -r '.max_dev_builds // 8' "$INFRA" 2>/dev/null || echo 8)
  rid=$(jq -r '.rollout_id' "$INFRA")
  k=$(next_k)
  if [ "$k" -gt "$max" ]; then
    die "development build cap reached ($max). Submit what you have with ./submit.sh."
  fi
  if [ "$k" -gt 1 ] && [ "$(jq -r '.status // "pending"' "$STATE/b$((k-1)).json")" = "pending" ]; then
    die "build $((k-1)) is still running — run: ./devbuild.sh wait $((k-1))"
  fi
  [ -f "$SEED_CFG" ] && { mkdir -p .revyl; cp "$SEED_CFG" .revyl/config.yaml; }
  git add -A
  git -c user.name="agent" -c user.email="agent@revyl-bench" \
      commit -q --allow-empty -m "dev build $k" || die "git commit failed"
  local out job
  out=$(revyl build --remote --profile development --platform ios --version "$rid-dev$k" \
        --no-set-current --detach --json 2>&1) || true
  job=$(printf '%s' "$out" | jq -r '.build_job_id // empty' 2>/dev/null || true)
  if [ -z "$job" ]; then
    printf '{"k":%d,"status":"refused","commit":"%s","error":%s}\n' "$k" "$(git rev-parse HEAD)" \
      "$(printf '%s' "$out" | tail -c 800 | jq -Rs .)" > "$STATE/b$k.json"
    die "the build queue refused the job: $(printf '%s' "$out" | tail -c 400)"
  fi
  printf '{"k":%d,"status":"pending","job":"%s","commit":"%s"}\n' "$k" "$job" "$(git rev-parse HEAD)" > "$STATE/b$k.json"
  jq --argjson n "$k" '.dev_builds_used = $n' "$INFRA" > "$INFRA.tmp" && mv "$INFRA.tmp" "$INFRA"
  echo "BUILD k=$k job=$job  (poll with: ./devbuild.sh wait $k)"
}

cmd_wait() {
  local k="$1"; [[ "$k" =~ ^[0-9]+$ ]] || die "usage: ./devbuild.sh wait <k>"
  local f="$STATE/b$k.json"; [ -e "$f" ] || die "no build $k"
  local job st deadline out vid
  job=$(jq -r '.job // empty' "$f"); [ -n "$job" ] || { echo "FAILED k=$k $(jq -r .error "$f")"; return 1; }
  deadline=$(( $(date +%s) + 300 ))
  while :; do
    out=$(revyl build status "$job" --json 2>/dev/null || echo '{}')
    st=$(printf '%s' "$out" | jq -r '.status // "unknown"')
    case "$st" in
      success)
        vid=$(printf '%s' "$out" | jq -r '.version_id // empty')
        jq --arg v "$vid" '.status = "ready" | .version_id = $v' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
        echo "READY k=$k version-id=$vid"
        echo "next: revyl dev --platform ios --no-build --build-version-id $vid --no-open --detach --json --timeout 900"
        return 0 ;;
      failed|error|errored|cancelled|canceled|timeout|timed_out|refused)
        jq '.status = "failed"' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
        echo "FAILED k=$k status=$st $(printf '%s' "$out" | jq -r '.error // ""')"
        echo "--- compiler output (build status --debug, lines around the first error:) ---"
        revyl build status "$job" --debug 2>&1 | grep -n -E 'error:|\*\* BUILD FAILED' | head -1 | cut -d: -f1 \
          | xargs -I{} sh -c 'revyl build status "$0" --debug 2>&1 | sed -n "{},\$p" | grep -v "compilation-cache\|swift compiler caching" | head -40' "$job" || true
        return 1 ;;
    esac
    if [ "$(date +%s)" -ge "$deadline" ]; then echo "PENDING k=$k status=$st (call wait again)"; return 2; fi
    echo "$(date -u +%H:%M:%S) k=$k status=$st"
    sleep 20
  done
}

cmd_status() {
  local max used k
  max=$(jq -r '.max_dev_builds // 8' "$INFRA"); used=$(jq -r '.dev_builds_used // 0' "$INFRA")
  k=$(( $(next_k) - 1 ))
  echo "development builds used: $used/$max"
  [ "$k" -ge 1 ] && echo "last k=$k status=$(jq -r .status "$STATE/b$k.json") version-id=$(jq -r '.version_id // "-"' "$STATE/b$k.json")"
  return 0
}

case "${1:-build}" in
  build|"") cmd_build ;;
  wait)     cmd_wait "${2:-}" ;;
  status)   cmd_status ;;
  *)        die "usage: ./devbuild.sh [build|wait <k>|status]" ;;
esac
