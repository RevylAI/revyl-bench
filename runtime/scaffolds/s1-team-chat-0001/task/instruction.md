# TeamChat — build a mobile team-chat app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a team-chat app: workspace
channels with unread badges, a per-channel message timeline ordered by an integer sort
key, a composer with @mentions rendered as highlighted tokens, threaded replies with a
reply count on the parent, a Mentions inbox, and per-channel notification settings
(mute + mention-only) with a textual summary that persists across navigation.

The work is split into three steps (see `steps/01-tabs`,
`steps/02-channels-timeline-mentions`, `steps/03-threads-settings`, each with its own
`instruction.md`), followed by a final end-to-end acceptance run. Complete the steps in
order.

## How your work is verified

After each submission, **hidden device tests** run your app on a real cloud iOS
simulator and grade journeys with screenshot validations. You never see the test
definitions. Every submission is graded against the **full suite** — all step tests
plus the final e2e — so a change that breaks an earlier step's behavior is caught
immediately. If a run fails, you receive the run report (failed-criteria text,
per-step verdicts, screenshots); fix your code and resubmit. Every requirement the
tests check is stated in this contract and the step contracts; nothing hidden is
required beyond what is written here.

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Integer sort key; no live timestamps.** Every message carries an integer
   `tsOrder`. Timelines, thread replies, and the Mentions inbox render in ascending
   `tsOrder`. A newly sent message or reply gets `tsOrder = (current maximum) + 1`, so
   it always appears **last** (at the bottom). No time-of-day text is rendered anywhere.
2. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. Unread counts are seeded
   integers (not derived from anything live). Message ids for sent messages come from a
   counter. Every value on screen must be computable from this contract alone.
3. **Debounced one-shot Send / Reply.** The channel composer's Send and the thread's
   Reply are one-shot: a rapid double-tap sends **exactly one** message. Disabling the
   button briefly after press (≈250–300 ms) is one acceptable implementation. Both are
   disabled while the input is empty/whitespace; sending trims and clears the input.
4. **Verbatim text input.** Both text inputs (composer and thread reply) have
   auto-capitalization and auto-correct **disabled**, so a body typed as
   `shipping now` is stored and rendered exactly as `shipping now`.
5. **Mentions are highlighted tokens.** In every rendered message body (timeline,
   thread, Mentions inbox), each `@<handle>` token (regex `@(\w+)`, handle matched
   case-insensitively against the seed users) renders as a **visually distinct
   highlighted token** — a different text colour on a tinted background pill is the
   reference look — while the rest of the body is plain text. Colour choice is yours;
   the highlight must be obvious in a screenshot. (Highlighting an `@token` whose
   handle is not a seed user is allowed; no test types one.)
6. **Textual state summaries.** Reply counts, the muted-channels list, and the
   mention-only state are exact text strings (pinned below) — never encoded only in
   colours, badges, or switch positions. (Badges/switches accompany the text.)
7. **Mute has no side effects beyond Settings.** Muting a channel or enabling
   mention-only changes only the notification state and the Settings summary text.
   Unread badges on the Channels tab and the rows of the Mentions inbox are unaffected.
8. **State survives navigation.** Sent messages, thread replies, per-channel mute
   state, and the mention-only toggle persist when the user navigates between tabs and
   pushes/pops screens (module-level/store state is sufficient; no backend, no disk
   persistence — a fresh install starts from the seed below).
9. **Navigation shape.** The app opens directly on the Channels tab — no login,
   onboarding, or splash gate — and the channel list is interactive within two seconds
   of launch. The three tabs are a bottom tab bar. Opening a channel
   **pushes** a channel screen (native stack header titled `#<name>` with a back
   button); tapping any message row in a channel timeline **pushes** its thread screen
   (native stack header titled `Thread` with a back button). Back from the thread
   returns to the channel; back from the channel returns to the tab bar. Every message
   row (with or without existing replies) is tappable to open its thread — no separate
   "reply" affordance is required.

## Seed data (exact values — copy these verbatim)

Users (`id`, `handle` without the `@`, `displayName`). The signed-in user is
`user-you`; messages you send are authored by `You`.

| id | handle | displayName |
|---|---|---|
| user-you | you | You |
| user-alex | alex | Alex Rivera |
| user-sam | sam | Sam Chen |
| user-jordan | jordan | Jordan Blake |

Channels (`id`, `name` without the `#`, `unreadCount`), in this order:

| id | name | unreadCount | renders as |
|---|---|---|---|
| ch-general | general | 3 | `#general` + badge `3` |
| ch-engineering | engineering | 5 | `#engineering` + badge `5` |
| ch-design | design | 0 | `#design` — **no badge** (badge only when count > 0) |
| ch-random | random | 2 | `#random` + badge `2` |
| ch-announcements | announcements | 1 | `#announcements` + badge `1` |

Messages (`id`, channel, author, `body`, `tsOrder`, `parentId`). `parentId` non-null
marks a threaded reply (shown in the parent's thread, **not** in the channel timeline).
`mentions` is derived from the body's `@handle` tokens.

| id | channel | author | body | tsOrder | parentId |
|---|---|---|---|---|---|
| msg-gen-1 | general | Alex Rivera | Morning all! Kicking off the sprint today. | 1 | — |
| msg-gen-2 | general | Sam Chen | Standup notes are in the shared doc. | 2 | — |
| msg-gen-3 | general | Jordan Blake | @you can you review the onboarding copy? | 3 | — |
| msg-gen-4 | general | Alex Rivera | Thanks @sam for the notes. | 4 | — |
| msg-gen-5 | general | You | Got it, reading now. | 5 | msg-gen-2 |
| msg-eng-1 | engineering | Sam Chen | Deploy pipeline is green again. | 6 | — |
| msg-eng-2 | engineering | Alex Rivera | @you the flaky test is fixed on main. | 7 | — |
| msg-eng-3 | engineering | Jordan Blake | Nice, merging my PR then. | 8 | — |
| msg-eng-4 | engineering | You | Can someone review PR-1423? | 9 | — |
| msg-eng-5 | engineering | Sam Chen | On it. | 10 | msg-eng-4 |
| msg-des-1 | design | Jordan Blake | New color tokens are in Figma. | 11 | — |
| msg-des-2 | design | Alex Rivera | Love the new palette. | 12 | — |
| msg-des-3 | design | Sam Chen | Should we bump the border radius? | 13 | — |
| msg-des-4 | design | Jordan Blake | Let's discuss in the design sync. | 14 | — |
| msg-rand-1 | random | Alex Rivera | Coffee run in 10? | 15 | — |
| msg-rand-2 | random | Sam Chen | Always yes. | 16 | — |
| msg-rand-3 | random | Jordan Blake | Bringing donuts too. | 17 | — |
| msg-rand-4 | random | You | You're the best. | 18 | — |
| msg-ann-1 | announcements | Alex Rivera | All-hands moved to Friday 3pm. | 19 | — |
| msg-ann-2 | announcements | Jordan Blake | @you please share the roadmap slides. | 20 | — |
| msg-ann-3 | announcements | Sam Chen | Office closed next Monday. | 21 | — |
| msg-ann-4 | announcements | Alex Rivera | Welcome our new teammate! | 22 | — |

Defaults: no channel muted; mention-only off; no messages sent. Next `tsOrder` for a
sent message is 23.

Derived values (the tests assert these exact strings and orders):

- `#general` timeline (top-level only, ascending): Alex Rivera "Morning all! Kicking
  off the sprint today." → Sam Chen "Standup notes are in the shared doc." (with the
  reply-count text `1 reply`, because msg-gen-5 is its reply) → Jordan Blake "@you can
  you review the onboarding copy?" → Alex Rivera "Thanks @sam for the notes.". A message
  sent from the composer appears after these, at the bottom, authored by `You`.
- Reply count text: `<n> reply` when n = 1, `<n> replies` otherwise; shown on a
  timeline row only when n > 0, and always in the thread header under the parent.
  Thread of msg-gen-2 initially: parent "Standup notes are in the shared doc." (Sam
  Chen), `1 reply`, one reply "Got it, reading now." (You). After posting one reply:
  `2 replies`, and the new reply is listed last.
- Mentions inbox (messages whose body mentions `@you`, ascending tsOrder): `Jordan
  Blake in #general` — "@you can you review the onboarding copy?"; `Alex Rivera in
  #engineering` — "@you the flaky test is fixed on main."; `Jordan Blake in
  #announcements` — "@you please share the roadmap slides.". Sending a message that
  mentions someone else (e.g. `@alex`) does not add a row here.
- Settings summary: `Muted: none` and `Mention-only: Off` by default; muting one
  channel → `Muted: #<name>` (several → comma-space separated in the order muted);
  turning mention-only on → `Mention-only: On`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Channels`, `Mentions`, `Settings`. Each tab screen shows its
  heading text: `Channels`, `Mentions`, `Settings`.
- Channels tab: one row per channel in seed order showing `#<name>` and, when
  `unreadCount > 0`, a small numeric badge with the count.
- Channel screen: header title `#<name>`; each timeline row shows the author's
  `displayName` above the body (mentions highlighted) and, when it has replies, the
  reply-count text; a text input pinned at the bottom with placeholder
  `Message #<name>` and a button labelled `Send` to its right.
- Thread screen: header title `Thread`; the parent message (author + body) at the
  top, followed by the reply-count text (`1 reply` / `2 replies` …), then the replies
  in ascending order (author + body); a text input pinned at the bottom with placeholder
  `Reply in thread` and a button labelled `Reply` to its right.
- Mentions tab: one row per mentioning message showing `<Author displayName> in
  #<channel>` above the body with the `@you` token highlighted; when empty, the text
  `No one has mentioned you yet.`.
- Settings tab: a `Summary` block with the two lines `Muted: <list or none>` and
  `Mention-only: On|Off`; a `Mute channels` section with one row per channel (seed
  order) labelled `#<name>` with a toggle switch; an `Alerts` section with one row
  labelled `Mention-only` with a toggle switch.

## Final acceptance

The final e2e journey: launch → Channels tab lists the five channels → tap `#general` →
timeline in seed order with the composer at the bottom → type `@sam deploy is green`
→ Send → the message appears once at the bottom from `You` with `@sam` highlighted →
tap Sam Chen's "Standup notes are in the shared doc." row → thread shows the parent,
`1 reply`, and the existing reply → type `shipping now` → Reply → `shipping now` listed
and `2 replies` → back → back → Settings tab → turn on the `#design` mute switch and
the `Mention-only` switch → `Muted: #design`, `Mention-only: On` → Channels tab →
Settings tab → both still `Muted: #design`, `Mention-only: On` →
Mentions tab lists the `@you` rows (e.g. `Jordan Blake in #general`). It must complete
without manual intervention.
