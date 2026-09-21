#!/usr/bin/env bash
# provision/build_images.sh [harness ...]
# Builds revyl-bench-runner:v1 and one agent image per (harness × SDK) from the registry.
# The harness install line comes from contestants/registry.yaml (pinned versions), so
# rebuilding after a pin change is the ONLY way a contestant's software changes.
#   ./provision/build_images.sh                 # runner + every harness in the registry, SDKs 56 57
#   ./provision/build_images.sh claude-code     # runner + just that harness
#   SDKS="57" ./provision/build_images.sh claude-code
set -eo pipefail
cd "$(dirname "$0")/.."
SDKS="${SDKS:-56 57}"
# revyl CLI pin — the Dockerfiles COPY image/REVYL_CLI_VERSION themselves and assert the installed
# binary matches it; there is deliberately no override knob: one file is the pin.
PIN="$(tr -d '[:space:]' < image/REVYL_CLI_VERSION)"
[ -n "$PIN" ] || { echo "FATAL: image/REVYL_CLI_VERSION is empty" >&2; exit 1; }
echo "== revyl CLI pin: $PIN (image/REVYL_CLI_VERSION)"
# Drift tripwire: the pin file must be the ONLY literal CLI version in runtime/. A stray
# `REVYL_VERSION=v0.1.xx` in a Dockerfile/script is exactly how the 0.1.82 -> 0.1.95 -> 0.1.96
# bumps went stale in three places at once (2026-08-24/25).
if grep -rnE 'REVYL_VERSION=v?0\.1\.[0-9]+' --include='Dockerfile*' --include='*.sh' --include='*.py' \
     --exclude-dir=runs --exclude-dir=campaigns --exclude-dir=hosts --exclude-dir=scaffolds --exclude-dir=node_modules . | grep -v 'build_images.sh'; then
  echo "FATAL: hard-coded revyl CLI version found above — use image/REVYL_CLI_VERSION" >&2; exit 1
fi

echo "== runner"
docker build -f image/Dockerfile.runner -t revyl-bench-runner:v1 .

# harness → rendered install line, from the registry (python does the ${...} substitution).
# Captured via $(...) + rc check, NOT mapfile < <(...): a process substitution's exit code
# is invisible to set -e, so a registry parse failure would silently build zero agent
# images and exit 0 (observed 2026-08-20: unquoted ": " in invoke_resume broke the YAML).
PARSED=$(python3 - "$@" <<'PY'
import sys, yaml, re
reg = yaml.safe_load(open("contestants/registry.yaml", encoding="utf-8"))
want = set(sys.argv[1:])
seen = {}
for slug, e in reg["contestants"].items():
    h = e["harness"]
    if want and h not in want: continue
    inst = re.sub(r"\$\{(\w+)\}", lambda m: str(e.get(m.group(1), m.group(0))), e["install"])
    seen.setdefault(h, inst)          # first entry per harness wins (same pin per harness)
for h, inst in seen.items():
    print(f"{h}\t{inst}")
PY
) || { echo "FATAL: contestants/registry.yaml failed to parse — no agent images built" >&2; exit 1; }
[ -n "$PARSED" ] || { echo "FATAL: no harness matched '$*' in the registry" >&2; exit 1; }
mapfile -t LINES <<<"$PARSED"
for line in "${LINES[@]}"; do
  h="${line%%$'\t'*}"; inst="${line#*$'\t'}"
  for sdk in $SDKS; do
    tag="revyl-bench-agent:${h}-sdk${sdk}"
    echo "== $tag   ($inst)"
    docker build -f image/Dockerfile.agent --build-arg SDK="$sdk" --build-arg HARNESS_INSTALL="$inst" -t "$tag" .
  done
done
docker images | grep -E "revyl-bench-(agent|runner)"
