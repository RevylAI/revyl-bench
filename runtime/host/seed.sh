#!/usr/bin/env bash
# seed.sh — populate the rollout's `workspace` named volume from the scaffold copy
# Runs ONCE per rollout in a throwaway container of the AGENT image
# (`docker run --rm -u agent -v <vol>:/workspace -v <host>/seed:/seed:ro --entrypoint bash
#  <agent image> /seed/seed.sh <expected base_commit> <rollout_id>`), so file ownership is
# uid 1000 and git runs on Linux (no CRLF / filemode drift between the launch machine and the host).
#
# Two commits, on purpose:
#   1. "base" — the scaffold exactly as provisioned. Committed with FIXED author/committer
#      dates + identity and core.filemode=false, so the sha is a pure function of the tree:
#      it MUST equal task.toml [agent].base_commit (computed the same way by
#      the scaffold generator). Mismatch = the scaffold changed after provisioning →
#      abort (the task's base_commit would silently lie in every attempts.jsonl row).
#   2. "seed <rollout_id>" — the rollout-specific files: RUNBOOK.md, infra_runtime.json.
#      (Until 2026-08-25 this step also rewrote .revyl/config.yaml project.name to the
#      rollout id "to attribute dev sessions to the rollout". The canonical config of CLI
#      >= 0.1.95 has no project.name (server-owned), the server never recorded it on
#      sessions anyway, and per-rollout teardown works from the rollout's own
#      .revyl/device-sessions.json snapshot — so the rewrite is gone, not migrated.)
# The repo never had a remote — nothing to strip; asserted anyway.
set -eo pipefail
EXPECTED="$1"; RID="$2"
cd /workspace
[ -z "$(ls -A /workspace 2>/dev/null)" ] || { echo "seed: /workspace not empty" >&2; exit 2; }

# 1. base tree
tar -C /seed/scaffold -cf - . | tar -xf -
git init -q -b main
git -c core.filemode=false add -A
GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z" \
git -c user.name=revyl-bench -c user.email=bench@revyl.ai -c core.filemode=false \
    commit -q -m "base: scaffold" --no-gpg-sign
BASE=$(git rev-parse HEAD)
if [ "$BASE" != "$EXPECTED" ]; then
  echo "seed: base_commit mismatch: got $BASE want $EXPECTED (scaffold drifted after provisioning)" >&2
  exit 3
fi

# 2. rollout-specific layer
cp /seed/RUNBOOK.md ./RUNBOOK.md
cp /seed/infra_runtime.json ./infra_runtime.json
# native (swift) rollouts: the agent's development build recipe (launch_rollout renders it
# with this rollout's dev app id) replaces the scaffold's stub; devbuild.sh re-copies it
# from .devbuilds/ (gitignored below) before every build so an edit cannot break the loop.
if [ -f /seed/devbuild-config.yaml ]; then
  mkdir -p .revyl .devbuilds
  cp /seed/devbuild-config.yaml .revyl/config.yaml
  cp /seed/devbuild-config.yaml .devbuilds/recipe.yaml
fi
# submit.sh is an image-owned symlink installed by entrypoint.sh — environment, not agent
# source. If committed, its absolute link target trips the runner's safe-tar filter.
printf '
# revyl-bench environment shims (never part of a submission)
submit.sh
devbuild.sh
.devbuilds/
checkpoint.sh
' >> .gitignore
# Refuse to seed a scaffold whose .revyl/config.yaml is still in the legacy shape: every
# `revyl dev` / `revyl device` call the agent makes from /workspace would be refused by the
# CLI ("local configuration uses a legacy format") and read as agent incompetence.
if [ -f .revyl/config.yaml ] && { grep -qE '^(hotreload:|defaults:)|^\s+system: Expo' .revyl/config.yaml \
                                  || ! grep -qE '^\s+id: [0-9a-f-]{36}$' .revyl/config.yaml; }; then
  echo "seed: .revyl/config.yaml is not the CANONICAL shape (needs project.id; legacy project.name/build.system/hotreload is refused by CLI >= 0.1.95); regenerate the scaffold with provision/make_scaffold.py" >&2
  exit 5
fi
git config core.filemode false
git add -A
git -c user.name=revyl-bench -c user.email=bench@revyl.ai commit -q -m "seed: rollout $RID" --no-gpg-sign
[ -z "$(git remote -v)" ] || { echo "seed: unexpected git remote" >&2; exit 4; }
echo "seed: ok base=$BASE head=$(git rev-parse HEAD)"
