#!/usr/bin/env bash
# entrypoint.sh — PID 1 of the agent container. Runs as user `agent`.
#
# Inputs (from compose):
#   /invoke.sh          the contestant's invoke line, already ${...}-substituted from the
#                       registry by launch_rollout (e.g. `claude -p "$(cat RUNBOOK.md)" ...`)
#   env  REVYL_API_KEY  agent-org key (agent.env); <key_env> the model credential
#   /workspace          scaffold @ base_commit + task/ + RUNBOOK.md + infra_runtime.json
#   /mailbox/{submit,feedback}
#   /log/harness.log    where the harness's stdout/stderr is tee'd (the runner reads
#                       nothing else from the agent side except at END)
#
# It does exactly three things: make the workspace runnable (deps), install the submit
# shim, run the harness once. When the harness exits (for any reason) the container
# exits; launch_rollout notices and tells the runner (control/harness_exit.json).
set -eo pipefail
export HOME=/home/agent
export PATH="$HOME/.revyl/bin:/usr/local/bin:$PATH"
cd /workspace

echo "[entrypoint] $(date -u +%FT%TZ) rollout=$(jq -r .rollout_id infra_runtime.json 2>/dev/null) user=$(id -un)"
# Evidence line: which CLI this rollout actually ran (the pin is /opt/bench/REVYL_CLI_VERSION;
# the image build asserted equality, this just records it next to the rollout id).
echo "[entrypoint] revyl CLI: $(revyl --version 2>&1) (pin $(cat /opt/bench/REVYL_CLI_VERSION 2>/dev/null))" | tee -a /log/harness.log

# 1. deps — the scaffold is committed WITHOUT node_modules. npm ci is exact
#    (package-lock.json is part of base_commit), so every rollout of a task starts from
#    the same dependency tree. A native Swift scaffold has no package.json: nothing to
#    install, its compiler is on Revyl's build runner (devbuild.sh).
if [ -f package.json ] && [ ! -d node_modules ]; then
  echo "[entrypoint] npm ci …"
  npm ci --no-audit --no-fund 2>&1 | tail -3
elif [ ! -f package.json ]; then
  echo "[entrypoint] no package.json (native scaffold): skipping npm ci"
fi

# 2. submit shim — a symlink so `./submit.sh` works from /workspace but the script itself
#    is image-owned (the agent cannot edit it in place; the RUNBOOK also forbids touching it).
ln -sf /opt/bench/submit.sh ./submit.sh
# checkpoint.sh — an UNSCORED step marker. Advertised in RUNBOOK.md as of
# protocol 5: the agent is told to run it after each step, so every rollout leaves
# step-boundary trees whether or not it struggles. Protocol-4 rows never aggregate with
# protocol-5 rows.
ln -sf /opt/bench/checkpoint.sh ./checkpoint.sh
# devbuild.sh — the native (Swift) agent's remote development build; the Expo runbook
# never mentions it and the Expo tree has no `development` recipe for it to run.
ln -sf /opt/bench/devbuild.sh ./devbuild.sh

# 3. git identity for the harness's own commits (submit.sh sets its own -c identity)
git config user.name  >/dev/null 2>&1 || git config user.name "agent"
git config user.email >/dev/null 2>&1 || git config user.email "agent@revyl-bench"

# 3b. per-harness setup, if the registry gave one. opencode keeps its credential in
#     ~/.local/share/opencode/auth.json and prompts for tool permissions unless told
#     otherwise; with no tty an unanswered prompt hangs the whole rollout. Harnesses that
#     need nothing get an empty file.
if [ -s /setup.sh ]; then
  echo "[entrypoint] harness setup …"
  bash /setup.sh || { echo "[entrypoint] setup.sh failed" >&2; exit 65; }
fi

# 4. run the harness. The invoke line is mounted at /invoke.sh (launch_rollout renders it
#    from the registry; a file, not an env var, because compose would try to interpolate
#    the `$(cat RUNBOOK.md)` inside it). `bash /invoke.sh` runs it in /workspace.
INVOKE_FILE="${BENCH_INVOKE_FILE:-/invoke.sh}"
[ -s "$INVOKE_FILE" ] || { echo "[entrypoint] $INVOKE_FILE missing/empty" >&2; exit 64; }
echo "[entrypoint] invoke: $(grep -v '^#' "$INVOKE_FILE" | tr '\n' ' ')"
# The harness session may END ITSELF while the rollout is still live (observed in an
# early rollout: Claude Code submitted, said "polling in the background", and exited — print
# mode terminates on the final message; there is no background). So: loop until the
# runner declares the rollout over (END.json). First iteration = the full invoke line;
# later iterations = the resume line from /invoke_resume.sh if the launcher provided one
# (e.g. `claude -p --continue …`, whose session state lives on the persisted home volume),
# else the full invoke again. Between iterations, wait out any in-flight grade so the
# resumed session wakes up to a fresh verdict instead of an empty mailbox.
set +e
iter=0
noprog=0
prev_req=""
while [ ! -f /mailbox/feedback/END.json ]; do
  iter=$((iter+1))
  # resume (not restart) when this rollout already has submission history — covers both
  # "harness ended itself mid-rollout" and "container was recreated mid-rollout"
  if [ -s /invoke_resume.sh ] && { [ "$iter" -gt 1 ] || ls /mailbox/submit/s*.request.json >/dev/null 2>&1; }; then
    RUN="/invoke_resume.sh"
  else
    RUN="$INVOKE_FILE"
  fi
  echo "[entrypoint] harness iteration $iter ($RUN) at $(date -u +%FT%TZ)" | tee -a /log/harness.log
  # PIPESTATUS[0], not $?: $? would be tee's exit code (always 0), and a crashed harness
  # would look like a clean exit to the retry logic below.
  bash "$RUN" 2>&1 | tee -a /log/harness.log
  rc=${PIPESTATUS[0]}
  # a clean exit resets the consecutive-failure streak the rc!=0 branch below counts
  if [ "$rc" -eq 0 ]; then
    infra=0
  fi
  echo "[entrypoint] harness exited rc=$rc (iteration $iter) at $(date -u +%FT%TZ)" | tee -a /log/harness.log
  [ -f /mailbox/feedback/END.json ] && break
  # if a submission is being graded, wait for its verdict before re-invoking (poll ≤35 min).
  # The sed replacement must be the two characters \1: the file carried a raw 0x01 byte
  # there, so last_req was a control character and every resume waited the full 35 min
  # for a verdict file that cannot exist (found 2026-09-03).
  last_req=$(ls /mailbox/submit/s*.request.json 2>/dev/null | sed -E "s/.*s([0-9]+)\.request.*/\1/" | sort -n | tail -1)
  # The verdict wait comes BEFORE any retry decision: a harness that submitted and then
  # crashed must not be re-invoked while its grade is in flight (a resumed session would
  # submit again without a verdict and the runner would grade two trees back to back).
  if [ -n "$last_req" ] && [ ! -e "/mailbox/feedback/s${last_req}.verdict.json" ]; then
    echo "[entrypoint] waiting for verdict s${last_req} before resuming …" | tee -a /log/harness.log
    for i in $(seq 1 70); do
      [ -e "/mailbox/feedback/s${last_req}.verdict.json" ] || [ -f /mailbox/feedback/END.json ] && break
      sleep 30
    done
    [ -f /mailbox/feedback/END.json ] && break
  fi
  # A resume that produces no new submission is not progress. Observed 2026-09-03: a
  # session resumed, edited for a few minutes, exited without submitting, and the loop
  # would have re-invoked it until the wall clock. Eight consecutive clean exits with no
  # new submission end the rollout as harness_exit (the model declining to submit).
  if [ "${rc:-0}" -ne 0 ]; then
    # a non-zero exit is the harness failing, not the model giving up (a model endpoint
    # that answers 5xx for a minute while it scales up would otherwise end the rollout at
    # k=0). Back off and retry within both limits.
    infra=$((${infra:-0}+1))
    if [ "$infra" -ge 10 ]; then
      echo "[entrypoint] ten consecutive harness failures (elapsed=${SECONDS}s) — stopping" | tee -a /log/harness.log
      # The stop marker is how the runner tells this apart from "the model declined to
      # submit" (the no-progress branch below): both end the container, but this one is
      # the harness failing to run at all — a provider 5xx, or a session that can never
      # resume (e.g. it holds more images than the provider accepts in one request). The
      # model never got a turn, so the
      # runner ends the rollout as `harness_crash` (a bench fault: voided and re-run),
      # not `harness_exit` (a scored outcome). /log here is ./harness-log on the host.
      printf '{"reason": "harness_crash", "rc": %s, "consecutive_failures": %s, "iteration": %s, "ts": "%s"}\n' \
        "$rc" "$infra" "$iter" "$(date -u +%FT%TZ)" > /log/harness_stop.json
      break
    fi
    echo "[entrypoint] harness failed rc=$rc ($infra/10) — retrying in 60 s" | tee -a /log/harness.log
    sleep 60
    continue
  fi
  if [ "${last_req:-0}" = "${prev_req:-0}" ]; then
    noprog=$((noprog+1))
    if [ "$noprog" -ge 8 ]; then
      echo "[entrypoint] eight consecutive exits with no new submission — stopping" | tee -a /log/harness.log
      # the model's decision, not a fault: the runner keeps `harness_exit` for this branch
      printf '{"reason": "no_progress", "rc": %s, "consecutive_no_progress": %s, "iteration": %s, "ts": "%s"}\n' \
        "${rc:-0}" "$noprog" "$iter" "$(date -u +%FT%TZ)" > /log/harness_stop.json
      break
    fi
  else
    noprog=0
  fi
  prev_req="$last_req"
  sleep 5
done
set -e
# Stop the dev-loop sessions THIS rollout left behind — by index, from /workspace's own
# .revyl/device-sessions.json (the CLI scopes `-s <index>` to the project dir in cwd).
# NEVER `revyl device stop --all` here: the agent org is shared by every parallel rollout
# and --all would kill the siblings' sessions mid-exploration (launch_rollout.py
# _stop_rollout_sessions is the teardown authority; this is belt-and-braces only). Failures
# are logged, not hidden: a silently failing stop is how device sessions leak.
if [ -f .revyl/device-sessions.json ]; then
  for idx in $(jq -r '.sessions[]?.index // empty' .revyl/device-sessions.json 2>/dev/null); do
    revyl device stop -s "$idx" >/dev/null 2>/tmp/stop.err \
      || echo "[entrypoint] device stop -s $idx failed: $(tail -c 300 /tmp/stop.err)" | tee -a /log/harness.log
  done
fi
exit "$rc"
