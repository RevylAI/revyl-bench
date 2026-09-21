# Step 02 — channel list, ordered timeline, composer with @mentions, Mentions inbox

Implement the Channels tab, the pushed channel screen, and the Mentions tab per the
root contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Channel list** (Channels tab): one row per seeded channel, in seed order, showing
   `#<name>` and a small numeric unread badge with the count when `unreadCount > 0`
   (`#general` 3, `#engineering` 5, `#random` 2, `#announcements` 1; `#design` shows no
   badge). Tapping a row pushes that channel's screen.
2. **Channel screen** (pushed, header title `#<name>`, native back button): the
   channel's top-level messages (replies excluded) in ascending `tsOrder`, each row
   showing the author `displayName` and the body with every `@handle` rendered as a
   highlighted token; rows with replies show `<n> reply` / `<n> replies`. A composer
   text input is pinned at the bottom (placeholder `Message #<name>`, verbatim input —
   no auto-capitalization/auto-correct) with a `Send` button to its right.
3. **Send** is one-shot (debounced) and idempotent: a rapid double-tap sends exactly one
   message. Sending appends a message authored by `You` with `tsOrder = max + 1` (so it
   appears at the bottom, exactly once), derives its mentions from the body, and clears
   the input. Send is disabled while the input is empty.
4. **Mentions tab**: lists every message (top-level or reply) whose body mentions
   `@you`, ascending `tsOrder`, each row showing `<Author displayName> in #<channel>`
   above the body with the `@you` token highlighted. With the seed alone this is
   `Jordan Blake in #general`, `Alex Rivera in #engineering`, `Jordan Blake in
   #announcements`. Empty state text: `No one has mentioned you yet.`.
5. Sent messages persist across navigation (store state; no backend needed).

## Observable outcome the hidden test checks

Launch → Channels lists general / engineering / design / random / announcements with
numeric badges on the channels that have unread messages → tap `#general` → timeline
shows "Morning all! Kicking off the sprint today." and "Standup notes are in the shared
doc." with the composer at the bottom → type `@alex ship it` → Send → the message
appears exactly once at the bottom from `You` with `@alex` highlighted → back → Mentions
tab lists rows with a highlighted `@you` such as `Jordan Blake in #general` and
`Alex Rivera in #engineering`.
