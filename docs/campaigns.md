# Campaigns — a benchmark run is a folder

A **campaign** is one benchmark run: one contestant, one purpose, one matrix of tasks ×
seeds, launched under one protocol on one image. It is a folder with a manifest that
says what ran, when, on which code, and whether it counts; inside it, one readable folder
per rollout with its own status file. The scorer reads campaigns and nothing else, and
"which runs made this number" is always answerable from one folder.

This page is the reference for anyone running or auditing an evaluation. The commands are
`runtime/campaign.py` (create, launch, inspect, mirror) and `runtime/score/score_v0.py
--campaign` (score); the library behind both is `runtime/campaigns.py`.

## Terminology

| term | meaning |
|---|---|
| **campaign** | one benchmark run, one folder, one manifest, one results row. Campaigns are never merged: comparing models is comparing campaigns. |
| **run** (rollout) | one contestant attempting one task once under one seed. One folder inside a campaign. Its immutable key is the **rollout id** (`<prefix>-<short>-s<seed>-<8hex>`), from which the build names are derived; the folder is named `<task>_s<seed>_<8hex>` for humans. |
| **cell** | one task in one campaign: the mean over that task's seeds. |
| **matrix** | the plan: which tasks × which seeds. The scorer compares what was collected against it and reports "2 of 3 seeds" rather than guessing. |
| **purpose** | why the campaign exists: `benchmark` (a results row), `calibration` (checking a task's difficulty before it is published), `seed-check` (verifying that a scaffold seeds and grades cleanly), `smoke` (infrastructure check), `experiment` (anything else). Purpose fixes the defaults and the initial legitimacy. |
| **lifecycle** | how far a run got, machine-written and forward-only: `launched → running → collected`, or a terminal fault `guard_abort`, `launch_failed`, `collect_failed`. |
| **legitimacy** | whether something is allowed to count. Campaign: `official`, `provisional`, `void`. Run: `valid`, `superseded`, `quarantined`, `void`, `adjudicated_ok`. Every human change carries a reason and is appended to a history with who and when. |
| **pipeline** | the code that graded a run: AMI id, runtime tree hash, revyl CLI pin, launching commit. Stamped at launch; the guard against grading on stale code. |
| **checks** | per-run verdicts that need the heavy artifacts (today: `phantom_fail` — a test the agent was told had failed although its device run completed with no failed step, which is a grading fault rather than an agent failure — and `suite_fetch` — the agent's transcript names this repository or its `grading-side/`, so it may have read the suites; the scorer excludes such a run until it is reviewed and set `adjudicated_ok`), computed once at collect while those artifacts are still local and stored in the status file. |
| **mirror** | the campaign tree copied to the object store under the same path. Mandatory at collect; afterwards the launch machine keeps only what scoring needs. |
| **complete** | every planned cell has a counted run for every planned seed. An incomplete campaign is aggregated with what it has and marked. |

## Layout

```
runtime/campaigns/
  2026-09-03_opencode-muse-spark-1.3_benchmark/       <date>_<contestant>_<purpose>[-<label>]
    campaign.json                                     the manifest
    scores.json                                       written by the scorer, never by hand
    launch.log                                        campaign.py launch's log
    logs/<task>_s<seed>_<ts>.log                      each rollout's launcher output
    runs/
      s1-commerce-0001_s1_004a4318/                   <task>_s<seed>_<8hex of the rollout id>
        status.json                                   lifecycle, pipeline, checks, mirror, legitimacy, history
        rollout.json  attempts.jsonl                  the scoring inputs — always kept locally
        reports/ feedback/ submit/ transcript/ ...    mirrored at collect; removed locally afterwards
                                                      by default, for every purpose
```

Rules that hold everywhere:

- The path says what a run is, never whether it counts. Folders are never moved; standing
  lives in `status.json`.
- The rollout id and everything derived from it (build version names, archive keys inside
  `rollout.json`) never change. Only the folder name is readable.
- The object store holds the identical tree under `campaigns/…`. `campaign.py fetch`
  brings a run's heavy artifacts back on demand.
- The manifest's `runs` list is a cache that `campaign.py` rebuilds from the status
  files. The status files are the truth; concurrent rollouts each write their own and
  never touch the manifest.

## `campaign.json`

| field | written by | meaning |
|---|---|---|
| `campaign` | `new` | the folder name |
| `purpose` | `new` | see the table above |
| `created_at`, `created_by` | `new` | when and who (`--by` or the login name) |
| `contestant` | `new` | `slug`, `short`, `model`, `harness`, `harness_version` from the registry |
| `protocol_version` | `new` | the registry's protocol at creation |
| `matrix` | `new`, `extend` | `tasks`, `seeds`, `cap`, `wall_clock_min`, `transport`, `mode`, `ssh_ip` (`private` when launching from a control host inside the cloud network, `public` from a workstation; taken from `--ssh-ip` or `REVYL_BENCH_SSH_IP` at creation and exported to every rollout by `launch`) |
| `slim_after_mirror` | `new` | whether the heavy artifacts leave the launch machine after a successful mirror (true for every purpose; `--keep-artifacts` overrides) |
| `pipeline` | `new` | the pin at creation: `ami_id`, `runtime_tree_hash`, `revyl_cli_version`, `launch_commit`, `dirty` |
| `legitimacy` | `new`, `set` | `status`, `reason`, `set_by`, `set_at` |
| `history` | every writer | append-only: `created`, `extended`, `legitimacy` events |
| `runs` | `campaign.py` | the cache of the runs' status files |
| `notes` | `new` | free text |

Purpose decides the initial legitimacy: `benchmark` and `calibration` start `official`,
`seed-check` starts `provisional`, `smoke` and `experiment` start `void`. A benchmark
plans seeds 1, 2, 3, the scoring spec's cell; narrowing it below three seeds needs
`--reason` and starts the campaign `provisional`, so a one-seed benchmark is never
`official` by construction.

## `status.json` (per run)

| field | written by | meaning |
|---|---|---|
| `rollout_id`, `campaign`, `task`, `seed`, `contestant_slug`, `protocol_version`, `harness_version`, `mode`, `created_at` | launch | the cell, copied from `rollout.json` so `cat status.json` shows it |
| `lifecycle` | launch, collect | forward-only; a later step can never move it backwards |
| `pipeline` | launch, collect | what graded the run: the AMI's tree hash for `ec2` (the checkout's for `local`), the AMI id, the CLI pin, the launch commit; `attempts_sha256` at collect, so an in-place re-grade is visible |
| `checks` | collect | `phantom_fail`, `phantom_slots`, `reports_seen`, `suite_fetch`, `suite_fetch_hits`, `transcripts_seen`, `at`, `by`; `null` until collect |
| `mirror` | collect, `sync` | `synced`, `at`, `prefix`, `error`; on a `local` transport `synced` is false with a `reason` |
| `legitimacy` | launch, `set` | `status`, `reason`, `set_by`, `set_at`; `valid` at launch |
| `history` | every writer | append-only rows: `ts`, `by`, what changed, `reason` |
| `fetched`, `slimmed`, `host`, `error`, `failed_guards` | launch, collect | context for the row that wrote them |

The lifecycle is written by `launch_rollout.py --campaign <name>` at each step:
`launched` right after the rollout is resolved, `running` once the containers are up,
`collected` after every artifact is fetched, `guard_abort` when a pre-flight guard fails
(the folder keeps a tombstone `attempts.jsonl`), `launch_failed` when anything between
`launched` and `running` fails, `collect_failed` when `attempts.jsonl` never arrived or
anything raised while waiting or collecting (the host is kept for salvage; `--resume`
finishes it). After a successful mirror the final `status.json` is pushed to the store
on its own, so the store never holds a draft that predates the mirror result.

## Running a campaign end to end

```
python3 runtime/campaign.py new --purpose benchmark --contestant opencode/muse-spark-1.3
python3 runtime/campaign.py launch --name 2026-09-03_opencode-muse-spark-1.3_benchmark --width 12
python3 runtime/campaign.py status --name 2026-09-03_opencode-muse-spark-1.3_benchmark
python3 runtime/score/score_v0.py --campaign 2026-09-03_opencode-muse-spark-1.3_benchmark
```

- **`new`** discovers the tasks (every package under `tasks/` for a benchmark;
  `--tasks a,b,c` narrows. The calibration and experiment purposes look for step-level
  packages, a task kind that is not part of this repository — give them `--tasks`), takes the seeds
  from the purpose (`--seeds` overrides), stamps the current pipeline, and writes the
  manifest. `--dry-run` prints it and creates nothing. `--label` distinguishes a second
  campaign on the same day; campaigns are never merged.
- **`launch`** runs every planned cell that has no collected run, `--width` at a time,
  each as one `launch_rollout.py --campaign` subprocess. It is resumable: a crashed
  campaign is relaunched with the same command, and cells with a live run are skipped.
  A `launch.lock` in the folder keeps two launchers off one campaign (a lock left by a
  dead launcher is replaced). It refuses to start when the pipeline recorded in the
  manifest differs from the current pin (a rebaked image, a new CLI): start a new
  campaign instead. `--only <task>` restricts it; `--only <task> --rerun` relaunches a
  finished cell and marks the old run `superseded` with the reason. `--dry-run` prints
  what would launch and writes nothing. At the end it names any finished cell whose run
  the scorer would still not count, so an unscorable run is set aside and relaunched
  instead of discovered later. For anything longer than a shell session:
  `setsid nohup python3 runtime/campaign.py launch --name … < /dev/null &`.
- **`status`** prints every planned cell with its runs, their lifecycle, legitimacy,
  mirror state and checks, then any run outside the matrix. It is read-only, so it is
  safe while a launch runs. **`list`** prints one line per campaign.
- **`set`** changes a campaign's legitimacy (`--legitimacy official|provisional|void`) or
  a run's (`--run <rollout_id> --legitimacy valid|superseded|quarantined|void|adjudicated_ok`).
  `--reason` is mandatory and lands in the history with who and when. One lifecycle
  write is a human's: `--run <rollout_id> --lifecycle launch_failed|collect_failed`
  moves a run whose launcher died (the machine rebooted, the connection dropped) from
  `launched`/`running` to a terminal fault, so its cell can be launched again. Setting a
  live run's legitimacy to `void` has the same effect on the cell.
- **`extend`** adds seeds or tasks to the matrix; the next `launch` fills the new cells.
  Refused when the pipeline moved, because a campaign never mixes grading code across its
  seeds.
- **`sync`** retries the mirror for final runs and pushes their latest `status.json`.
  When cleanup is enabled, it also re-syncs previously mirrored runs with local heavy
  artifacts and prunes only after that upload succeeds. Live runs are skipped.
  `sync --name <campaign> --slim` explicitly cleans older campaigns whose manifests
  kept artifacts. Upload failures preserve local files; cleanup failures are reported
  and retried by the next sync.
- **`fetch --run <rollout_id>`** pulls a run's artifacts back from the object store into
  its folder (its local `status.json` is never overwritten). `sync` and `fetch` both refuse
  on a `local`-transport campaign, which has no mirror.

Cleanup removes `reports/`, `feedback/`, `submit/`, `transcript/`, `final-evaluation/` and
`workspace.bundle`. It keeps the manifests, `attempts.jsonl`, the scoring metadata and
`harness.log`. Use `new --keep-artifacts` when you want the heavy artifacts to stay local.

A single rollout is launched into a campaign directly: `launch_rollout.py --task …
--contestant … --seed … --campaign <name>`. The campaign must exist and name the same
contestant and protocol; `--campaign` is required, so an ad-hoc rollout is a `smoke` or
`experiment` campaign of one cell (`campaign.py new --purpose smoke --tasks <task>`).
The live host's staging directory (seeded scaffold, `ec2.json` for `--resume`) is
`runtime/hosts/<rollout_id>/`, transient and never a record.

## How the scorer decides what counts

`score_v0.py --campaign <name>` reads the folder, prints a table and writes
`scores.json`. It never writes a status file: scoring a fetched copy has no side effects,
and the launch machine never drifts from the object store because someone scored it.
`--all` prints one headline line per campaign, with a `publ` column that says whether
the campaign could be published as it stands. The formula itself is
[`scoring.md`](scoring.md) and is unchanged; what follows is eligibility.

Every run ends in exactly one state:

| case | outcome |
|---|---|
| run folder without `status.json` or `rollout.json` | `unindexed`, not scored |
| lifecycle `launched` / `running` | `live`, not scored |
| lifecycle `guard_abort` / `launch_failed` / `collect_failed` | `tombstone`, not scored |
| run legitimacy `quarantined` or `void` | `excluded`, with the reason |
| run legitimacy `superseded` | `superseded`; the newer run of the cell counts |
| `rollout.json` disagrees with the manifest on contestant, harness version or protocol | `mismatch`, not aggregated |
| `mode` other than `full` | `excluded` |
| `attempts.jsonl` malformed, END missing or duplicated, no clean submission | `no_result`, with the reason |
| END is `harness_crash` (the harness failed to run 10 times in a row — a provider outage, a session the harness cannot resume) | `no_result`; collect already voided the run with that reason, so the cell is open and the next `launch` fills it. `harness_exit` (the model exited 8 times without submitting) is a scored outcome. |
| END carries violations | `adjudicate`; with legitimacy `adjudicated_ok` the run is scored and flagged |
| `checks.phantom_fail` is true | `phantom_fail`, excluded, unless `adjudicated_ok` |
| `checks.suite_fetch` is true | `suite_fetch`, excluded, unless `adjudicated_ok` |
| the same rollout id also sits in another campaign under the same root | `refused`: the same run filed twice, named on both sides |
| everything else | `scored` |

Then, over the scored runs:

- **Duplicate cell.** Two scored runs for one task and seed: the newer counts, ordered by
  `created_at` and then by rollout id (same-second launches exist). The older is listed
  under `problems` as a duplicate; nothing is written. Resolve it with
  `campaign.py set --run <old> --legitimacy superseded --reason …`.
- **Mixed contract versions.** A cell whose runs carry different `task_version` values is
  refused: they are different tests that share a name.
- **Outside the matrix.** A scored run whose task or seed is not planned is listed as a
  problem and not aggregated.
- **Cell** = mean over its counted seeds; a cell with fewer seeds than planned is
  aggregated with its actual n and marked incomplete. **Campaign** = macro mean over
  cells with data. `complete` is true when every planned cell has all its seeds.
- A `void` campaign aggregates nothing; runs are still listed. A `provisional` campaign
  aggregates but is never `publishable`. `publishable` means official, complete, and no
  problems.
- Flags that do not change the state: `unchecked` (no `checks` block; the artifacts are
  in the object store if the check has to run later), `unmirrored`,
  `provisional:no_task_version` (a legacy run with no recorded contract version).

## Publishing

Publishing is never a side effect of running or scoring. It is one explicit command:

- **`campaign.py promote --name <campaign> --row <row-id>`** writes the campaign into
  the committed official record, `results/official.jsonl`: one line per published row
  with the campaign, its contestant and protocol, the macro, the cells, every counted
  rollout id and score, the pipeline, and when it was promoted. It refuses, unless
  `--reason "…"` is given: a campaign whose legitimacy is not
  `official`; one whose `scores.json` says `complete: false`; one with entries under
  `problems`; one whose `scores.json` predates a status change (score again first); and
  a replacement of a row's campaign by another graded by the same pipeline (the audit
  trail for "re-ran until it improved"). A replaced row keeps `previous`.

`campaign.py render` also exists: it regenerates a leaderboard block on a results page that
carries `<!-- official:leaderboard -->` markers. The season-1 page is written by hand and has
none, so `render` is not part of publishing here.

So "which runs made this number" is always answerable from the record: each row lists the
campaigns behind it (a row may join several, for example when tasks were added later).

## `scores.json`

```json
{
  "campaign": "…", "scored_at": "…", "purpose": "benchmark", "legitimacy": "official",
  "contestant": {"slug": "…", "harness_version": "…"}, "protocol_version": 5, "matrix": {…},
  "records": [{"folder": "…", "rollout_id": "…", "task": "…", "seed": 1, "state": "scored",
               "score_pct": 73.2, "flags": [], "reason": null, "k_counted": 2, "O": 1.0, "…": "…"}],
  "aggregate": {"macro": 68.7, "cells": {"s1-commerce-0001": {"mean": 73.2, "n": 3, "planned": 3,
                "incomplete": false, "refused": false, "solved": true, "runs": ["…"]}},
                "cells_planned": 17, "cells_counted": 17, "seeds_planned": 51, "seeds_counted": 51,
                "solved": 15, "complete": true, "publishable": true},
  "problems": []
}
```

`records` has one entry per run folder with its state and, for scored runs, every field
of the score record. `aggregate` is `null` for a void campaign. `problems` is the list of
things a human has to look at before the campaign can be published.
