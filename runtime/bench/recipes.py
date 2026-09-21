"""bench.recipes — the ONE place that knows what a `.revyl/config.yaml` looks like.

Two renderings, one source of truth:

  * scaffold_config(pkg)   — the MINIMAL canonical config committed in scaffolds/<pkg>/
                             (project.id + session + build.framework, NO build recipe).
                             `technology="swift"` renders the native variant (framework: ios).
                             It is part of base_commit, so it must never change again:
                             every build detail lives in the template below instead.
  * build_recipe(pkg, …)   — the runner's GRADING recipe (runner/recipes/<technology>-preview.yaml.tmpl:
                             expo-preview for Expo/React Native, swift-preview for native SwiftUI)
                             rendered with the grading app id + iOS scheme; grade.py writes it
                             over the submission tree's config right before `revyl build --remote`.
                             The same template renders as a `development`/Debug profile
                             for the dev-client (the dev-client provisioning step).

Both carry the SAME deterministic project.id (uuid5 of the package name) so the runner's
overwrite can never be a "foreign" project id relative to the scaffold's.

This module is inside IMAGE_CODE_DIRS (bench/hosts.py) — a recipe change re-fingerprints the
runner image / AMI, which is exactly right: the recipe decides what binary gets graded.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path
from string import Template

# runner/recipes/ next to bench/ — on a checkout that is <repo>/runtime/runner/recipes, in the
# runner image /app/runner/recipes (Dockerfile.runner COPYs runner/ whole).
RECIPE_DIR = Path(__file__).resolve().parents[1] / "runner" / "recipes"

# task.toml [runtime.agent] technology → the framework line in .revyl/config.yaml and the
# grading recipe template. "expo" is the default (every task before 2026-09-19 is Expo and
# carries no `technology` key); "swift" is a native SwiftUI project built with xcodebuild.
TECHNOLOGIES = ("expo", "swift")
FRAMEWORK_FOR = {"expo": "expo", "swift": "ios"}

# Namespace for the deterministic project.id: uuid5(REVYL_PROJECT_NS, pkg). Deterministic on
# purpose — re-provisioning a scaffold must reproduce the same base_commit (the config file is
# part of the committed base tree). `revyl init -y` would mint a random uuid4 and `revyl config
# migrate` a PATH-derived uuid5, both of which change per checkout. The id is local-only: with
# no GitHub origin the CLI never reconciles it against a server-side project.
REVYL_PROJECT_NS = uuid.UUID("6f1c1a2e-5b7d-4e8a-9c3f-2d4b6e8a0c1d")


def project_id_for(pkg: str) -> str:
    return str(uuid.uuid5(REVYL_PROJECT_NS, pkg))


def ios_scheme(expo_name: str) -> str:
    """Port of `sanitizedName` in @expo/config-plugins/build/ios/utils/Xcodeproj.js — the
    Xcode project/scheme/workspace name `expo prebuild` derives from app.json `expo.name`:
        name.replace(/[\\W_]+/g, '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '')
    JS `\\W` is ASCII-only, hence the explicit class below (Python's `\\W` is Unicode-aware and
    would KEEP accented letters that JS strips). The `|| slugify(name) || 'app'` fallbacks
    only matter when nothing survives; our names are `bench-s1-<archetype>-0001` → e.g.
    `benchs1ridebooking0001`. The runner needs this to write `-workspace <scheme>.xcworkspace
    -scheme <scheme>` into the recipe — it cannot run `expo prebuild` itself (Linux, no Xcode),
    nor can a Windows launch machine (Windows refuses iOS prebuild)."""
    s = re.sub(r"[^A-Za-z0-9]+", "", expo_name)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not (0x0300 <= ord(ch) <= 0x036F))
    if not s:
        raise ValueError(f"expo.name {expo_name!r} sanitizes to nothing (node would fall back to 'app')")
    return s


def check_technology(technology: str) -> str:
    if technology not in TECHNOLOGIES:
        raise ValueError(f"technology must be one of {TECHNOLOGIES}, got {technology!r}")
    return technology


def scaffold_config(pkg: str, technology: str = "expo") -> str:
    """The canonical .revyl/config.yaml committed in every scaffold (revyl CLI >= 0.1.95).

    Carries a STUB build profile. `revyl config validate` accepts a profile-less config —
    that is what was measured on 2026-08-25 — but `revyl dev` is a different command and
    refuses one, with "no build profiles are configured", EVEN under `--no-build`. Since
    `revyl dev --no-build` is the command the agent's RUNBOOK tells it to run, a
    profile-less scaffold leaves the agent with no device loop at all, and that reads as
    agent incompetence rather than a provisioning fault. Measured 2026-08-27 on 0.1.96.

    The stub exists only to get `revyl dev` past that check. It is never used to build:
    the agent is told --no-build, and the grader overwrites this whole file with its
    image-owned recipe before `revyl build --remote`. Its build_commands fail loudly rather
    than silently producing an artifact, so a stray `revyl build` from the scaffold cannot
    be mistaken for a real one.

    The Swift variant differs only in `framework: ios` (measured 2026-09-19 on 0.1.96: that is
    what `revyl init --detect` writes for an .xcodeproj, and `revyl build --remote` refuses an
    Xcode tree under `framework: expo`)."""
    check_technology(technology)
    return f"""# Revyl CLI project configuration for the revyl-bench scaffold `{pkg}` (canonical shape,
# revyl CLI >= 0.1.95; generated by runtime/bench/recipes.py via provision/make_scaffold.py —
# do not hand-edit). project.id is uuid5(pkg): deterministic so base_commit is reproducible.
# The profile below is a STUB. `revyl dev` refuses a config with no build.profiles even
# under --no-build, which is the command the agent runs, so a profile-less scaffold means
# no device loop for anyone. Nothing builds from it: the agent passes --no-build and the
# grader overwrites this file with its own recipe before `revyl build --remote`.
project:
    id: {project_id_for(pkg)}
session:
    idle_timeout_seconds: 1800
build:
    framework: {FRAMEWORK_FOR[technology]}
    profiles:
        development:
            ios:
                build_commands:
                    - >-
                      echo "the scaffold config is a stub; the grader supplies the real
                      recipe (bench/recipes.py build_recipe)" >&2; exit 1
                output_path: build/app.tar.gz
"""


def build_recipe(pkg: str, *, app_id: str, scheme: str, profile: str = "preview",
                 configuration: str = "Release", template: Path | None = None,
                 technology: str = "expo") -> str:
    """Render runner/recipes/<technology>-preview.yaml.tmpl. `configuration` Release = baked JS
    (Expo) / optimised binary (Swift) — the only thing the grader may run; Debug = dev-client
    shell (Expo, `development` profile) or the agent's development build (Swift).
    Raises KeyError if the template has a placeholder we did not fill — a half-rendered recipe
    must never reach `revyl build`."""
    check_technology(technology)
    if not app_id or not scheme:
        raise ValueError(f"build_recipe needs app_id and scheme (got app_id={app_id!r}, scheme={scheme!r})")
    if profile == "preview" and configuration != "Release":
        raise ValueError("the preview profile must be a Release build — Debug boots the dev-client launcher")
    tmpl = (template or RECIPE_DIR / f"{technology}-preview.yaml.tmpl").read_text(encoding="utf-8")
    return Template(tmpl).substitute(project_id=project_id_for(pkg), app_id=app_id, scheme=scheme,
                                     pkg=pkg, profile=profile, configuration=configuration)
