# The task set

Twenty synthetic mobile apps, one per product archetype. Every task has the same
shape: a blank Expo/TypeScript scaffold, a product contract (a root specification plus
three cumulative step specifications), and a frozen 4-test device suite, withheld from the
agent at run time (one test per step plus a final end-to-end journey). Contracts pin every value (exact strings, exact
numbers, exact formats) so correctness is objectively judgeable from the device screen.
The apps are pure front end with fixed seed data: no clocks, no randomness, no network
backends.

The **suite blocks** column counts every block in a task's four tests — the taps and
scrolls that drive the journey, the short waits, and the validations that judge the screen
— a proxy for how much distinct behavior the task specifies. Validations alone are 14 to 33
per task; count them yourself from [`grading-side/`](../grading-side/README.md). All twenty tasks are **calibrated**: their
authoring checks are complete (see "How tasks are validated" below), which includes the
reference implementation passing every suite on three independent device runs. The last
column is the season-1 mean score of the five models that ran every task at three seeds
([results](season1-results.md)). The table is in authoring order.

| task | build this | suite blocks | season-1 mean score |
|---|---|---|---|
| **personal-finance** | budgeting app | 44 | 80.5 |
| **ride-booking** | ride-hailing app | 58 | 85.6 |
| **health-fitness** | workout tracker | 39 | 69.4 |
| **commerce** | shopping app | 49 | 82.0 |
| **food-delivery** | restaurant ordering | 56 | 74.6 |
| **team-chat** | messaging app | 54 | 74.0 |
| **habits** | habit tracker | 53 | 81.5 |
| **kanban** | task board | 53 | 82.0 |
| **league** | sports standings | 56 | 74.5 |
| **recipes** | meal planner | 53 | 76.5 |
| **split-bill** | expense splitting | 56 | 73.9 |
| **inventory** | warehouse stock (StockRoom) | 70 | 66.0 |
| **scheduler** | room booking (RoomBoard) | 72 | 74.8 |
| **gradebook** | weighted grades (MarkBook) | 70 | 78.3 |
| **payroll** | timesheets (ShiftPay) | 71 | 75.7 |
| **library** | lending desk (StackLend) | 69 | 67.7 |
| **till** | cash register (TillTape) | 72 | 76.4 |
| **invoicing** | invoices and payments | 83 | 76.3 |
| **bookings** | room booking with waitlists | 89 | 77.5 |
| **auctions** | silent auction with proxy bidding | 65 | 63.2 |

The first eleven tasks (personal-finance through split-bill) average about 52 blocks. The
nine after them are deliberately larger, 65 to 89 blocks, and harder in one specific way:
derivation depth, meaning multi-rule computations with exact, hand-checkable values. For
each of those nine, Revyl holds a derivation checker (not part of this repository) that
re-derives every number the suite asserts from the task's seed data. The till task's contract
additionally requires the app to write `AUDIT|…` log lines and tells the agent they are
graded from device logs. In season 1 they were not: the runner's log-assertion instrument
([`runtime/runner/observability.py`](../runtime/runner/observability.py)) was never
provisioned for till, so every till verdict and score comes from the four device tests alone.

## Why these can't be memorized

The apps are synthetic and never published — no repository, tutorial, or app-store
listing of a finished app exists for a model to have memorized. The contracts have been
public from the start, and since 2026-09-20 so are the test suites; a suite reveals the
order and phrasing of the checks, not values, because every value it asserts is already in
the contract. A model trained on data collected after that date may have seen both, and
its result should say so. What the benchmark measures is the
transfer skill: read a precise product contract, build it, verify it on a real device,
and repair it from evidence. Task sets rotate by season, and the generator that produces
them can produce new archetypes and new contracts faster than any could leak.

## Difficulty

Every task is solvable: before it grades anyone, a reference run (a solve by a capable
model with full access to the task) confirms the contract can be built as written and
passes its suite.

Season 1 measured how hard the tasks are for contestants. Across the five models that ran
every task at three seeds:

- **Easiest:** ride-booking (mean 85.6, every model solved every seed), then kanban and
  commerce (82.0).
- **Hardest:** auctions (63.2), inventory (66.0) and library (67.7). Inventory and library
  were each solved on every seed by only three of the five models.
- **Suite size is not difficulty.** Bookings has the largest suite (89 blocks) and is the
  seventh easiest task; health-fitness has the smallest (39) and is the fourth hardest.
- **Tasks separate models differently.** Auctions spans 44.8 to 87.6 across the five
  models and team-chat 44.8 to 83.4, while till spans only 70.7 to 82.1.

The same model also varies across seeds of one task: a first-submission pass on one seed
and a repair cycle on another is common, which is why every cell is the mean of three
seeds. Task sets rotate by season, and harder tiers are the generator's next seasons.

## How tasks are validated

Before a task can grade anyone, it passes a fixed set of authoring checks:

- **Contract solvability** — the reference run confirms the contract is internally
  consistent and buildable as written.
- **Device validation** — the suite runs against a reference build on real cloud
  simulators, confirming every checkpoint is reachable and judgeable from the device.
- **Stability evidence** — every frozen test is run repeatedly against a reference build
  and must return the same verdict each time before it is trusted to grade contestants.
- **A full pipeline attempt** — one complete rollout end to end, to confirm the task
  behaves correctly inside the evaluation machinery.

## What is in the repository, and what the agent sees

In the repository, per task: the full contract (`tasks/<task>/instruction.md` plus the step
contracts), the `task.toml` metadata including the frozen tests' names and the scaffold
pin, and — so that anyone can grade in their own organisations — the four test definitions
themselves, in [`grading-side/<task>/`](../grading-side/README.md). Publishing them costs
little because the contract already states every string they assert; what they add is the
checkpoints' order and phrasing.

What the agent under evaluation is given: the contract and the scaffold, nothing else.
`grading-side/` is never mounted into its container or copied into a scaffold, its Revyl
key cannot reach the organisation the tests live in, and it sees failures only as redacted
criterion text plus screenshots, and only for what failed. One limit: the container has
outbound network access and `allowed_hosts` in `task.toml` is not enforced by this runtime,
so an agent could fetch this public repository. A run whose transcript shows the agent
fetching this repository or its `grading-side/` is excluded from scoring (`suite_fetch`
check).

Held by Revyl: the authoring provenance and the stability evidence — the record of each
frozen test running repeatedly against a reference build before being trusted — available
for audit on request: open an issue in this repository.
