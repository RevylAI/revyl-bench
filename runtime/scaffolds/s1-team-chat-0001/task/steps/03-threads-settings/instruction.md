# Step 03 — threaded replies + persistent notification settings

Implement the thread screen and the Settings tab per the root contract.

## Requirements

1. **Open a thread**: tapping any message row in a channel timeline pushes the thread
   screen (header title `Thread`, native back button) showing the parent message
   (author + body) at the top, the reply-count text (`1 reply` / `2 replies` …), then
   the existing replies in ascending `tsOrder` (author + body). Example from the seed:
   Sam Chen's "Standup notes are in the shared doc." opens with `1 reply` and the reply
   "Got it, reading now." from `You`.
2. **Reply**: a text input pinned at the bottom (placeholder `Reply in thread`,
   verbatim input) with a `Reply` button — one-shot (debounced), disabled while empty.
   Posting appends the reply (authored by `You`, `tsOrder = max + 1`) to the thread and
   increments the reply count everywhere it is shown: the thread header (`2 replies`)
   and the parent's row back in the channel timeline.
3. **Settings tab**: a `Summary` block with `Muted: <list or none>` and
   `Mention-only: On|Off`; a `Mute channels` section with one toggle-switch row per
   channel labelled `#<name>` (seed order); an `Alerts` section with a `Mention-only`
   toggle-switch row. Turning a channel's switch on adds `#<name>` to the muted list
   (`Muted: #random`); turning `Mention-only` on renders `Mention-only: On`.
4. Both settings (and every sent message/reply) persist across navigation: leaving
   the Settings tab and returning shows the same summary text and the same switch
   positions (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Open `#general` → tap Sam Chen's "Standup notes are in the shared doc." → thread shows
the parent, an existing reply, `1 reply` → type `on it thanks` → Reply → `on it thanks`
appears and the count reads `2 replies` → back → back → Settings tab → turn on the
`#random` mute switch and the `Mention-only` switch → `Muted: #random`,
`Mention-only: On` → Channels tab → Settings tab → still `Muted: #random`,
`Mention-only: On`.
