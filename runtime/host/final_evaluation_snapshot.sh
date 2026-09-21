#!/usr/bin/env bash
# Trusted host helper: workspace is frozen and mounted read-only. Never invoke its
# hooks, filters, binaries, or npm scripts while selecting the final source tree.
set -euo pipefail
ws="${1:-/workspace}"
out="${2:-/output}"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
test -d "$ws/.git/objects"
git init -q --bare "$scratch/repo"
export GIT_DIR="$scratch/repo" GIT_WORK_TREE="$ws"
export GIT_ALTERNATE_OBJECT_DIRECTORIES="$ws/.git/objects"
cd "$ws"
# Start with the index so staged additions and ignored tracked files stay tracked.
# The separate index
# records modifications, removals, and nonignored new files without changing HEAD.
head=$(git -c safe.directory="$ws" --git-dir="$ws/.git" rev-parse HEAD)
if test -f "$ws/.git/index"; then
    cp "$ws/.git/index" "$scratch/repo/index"
else
    git read-tree "$head"
fi
# Agent index hints must not hide current working files. Clear them only in our
# private copy; NUL-delimited names also handle whitespace and embedded newlines.
git ls-files -z > "$scratch/tracked"
git update-index --no-skip-worktree -z --stdin < "$scratch/tracked"
git update-index --no-assume-unchanged -z --stdin < "$scratch/tracked"
if test -f "$ws/.git/info/exclude"; then
    cp "$ws/.git/info/exclude" "$scratch/repo/info/exclude"
fi
excludes=()
for part in node_modules .expo .cache __pycache__ .aws .ssh; do
    excludes+=(":(glob,exclude)**/$part/**")
done
for pattern in .env '.env.*' '*.pem' '*.key'; do
    excludes+=(":(glob,exclude)**/$pattern")
done
git -c core.autocrlf=false add -A -- . "${excludes[@]}"
# Never archive runtime caches or credential files, even if accidentally staged.
git ls-files -z | python3 -c '
import sys
blocked = {"node_modules", ".expo", ".cache", "__pycache__", ".aws", ".ssh"}
for name in sys.stdin.buffer.read().split(b"\0"):
    parts = name.decode("utf-8", "surrogateescape").split("/")
    leaf = parts[-1]
    if name and (blocked.intersection(parts) or leaf == ".env" or leaf.startswith(".env.") or leaf.endswith((".pem", ".key"))):
        sys.stdout.buffer.write(name + b"\0")
' | git update-index --force-remove -z --stdin
tree=$(git write-tree)
export GIT_AUTHOR_NAME="Revyl final workspace" GIT_AUTHOR_EMAIL="runner@revyl.local"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
commit=$(printf 'Final workspace snapshot\n' | git commit-tree "$tree" -p "$head")
# Keep the original history and refs, but add the final tree only in this private repo.
git -c safe.directory="$ws" --git-dir="$ws/.git" for-each-ref --format='%(objectname) %(refname)' |
while read -r oid ref; do git update-ref "$ref" "$oid"; done
git update-ref refs/heads/revyl-final-workspace "$commit"
git bundle create "$out/.workspace.bundle.tmp" --all
mv "$out/.workspace.bundle.tmp" "$out/workspace.bundle"
# Ignore export-ignore/export-subst attributes: the archive must equal the saved tree.
printf '* -export-ignore -export-subst\n' > "$scratch/repo/info/attributes"
mkdir "$scratch/attributes"
export GIT_WORK_TREE="$scratch/attributes" GIT_INDEX_FILE="$scratch/archive-index"
git archive --worktree-attributes --format=tar.gz -o "$out/.source.tar.gz.tmp" "$tree"
sha=$(sha256sum "$out/.source.tar.gz.tmp" | cut -d' ' -f1)
chmod 444 "$out/.source.tar.gz.tmp"
mv "$out/.source.tar.gz.tmp" "$out/source.tar.gz"
printf '{"sha256":"%s","commit_id":"%s","base_commit_id":"%s"}\n' "$sha" "$commit" "$head"
