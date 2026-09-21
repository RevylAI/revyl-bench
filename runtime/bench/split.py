"""Deterministic train/test assignment per rollout.

Every rollout is tagged "train" or "test" at launch so downstream consumers of the
collected rollouts agree on which ones they may touch. The tag is a
pure function of rollout_id — no stored state, no RNG at collection time — so it can
be re-derived for any rollout that already exists, and a re-run of extraction can
never re-deal the deck by accident. Changing TRAIN_FRAC or SALT does re-deal it;
bump SALT when that is done on purpose.

Note the tradeoff: a rollout-level split leaks task
identity — seeds of the same task produce near-identical apps — so held-out loss on
"test" rollouts measures memorisation resistance within known tasks, not
generalisation to unseen ones. Task-level holdout remains the stricter check.
"""
from __future__ import annotations

import hashlib

SALT = "split-v1"
TRAIN_FRAC = 0.70


def assign_split(rollout_id: str, train_frac: float = TRAIN_FRAC, salt: str = SALT) -> str:
    """"train" or "test", stable for a given (rollout_id, salt, train_frac)."""
    h = hashlib.sha256(f"{salt}:{rollout_id}".encode("utf-8")).digest()
    u = int.from_bytes(h[:8], "big") / 2**64
    return "train" if u < train_frac else "test"
