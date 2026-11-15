# Note template: one video → one note

You are extracting what **this creator** actually says in one video, so that later every piece
of advice in their skill can be traced back to them. Be faithful, not helpful:
- Only what is in the transcript. No outside knowledge, no "best practices" they didn't state,
  no fixing advice you disagree with.
- Paraphrase claims in plain words, and back each with a short verbatim quote (under 20 words)
  copied exactly from the transcript (never from the title or description).
- Transcripts come from captions or speech recognition, so expect small errors and no
  punctuation. Fix obvious mis-hearings in paraphrases; keep quotes as they are.
- Leave a section out entirely if the video has nothing for it. Don't pad.

Write `creators/<slug>/notes/<key>.md` in exactly this shape:

```markdown
---
key: <key>
content_type: <tutorial | opinion | story | review | promo>
sponsored: <false | true  # "<the verbatim sponsor mention>">
topics: [<1-4 kebab-case tags>]
---

## Summary
<one sentence: what this video is for>

## Claims
- <advice, rule of thumb or position, in plain words> — "<verbatim quote>"

## Frameworks
- <named method or ordered steps, exactly in their order>: 1) ... 2) ... 3) ...

## Examples
- <specific story, case or demo they use to make a point>

## Numbers
- <figure + what it refers to, as stated>

## Tools
- <product, app or resource they name> — <what they say about it>

## Voice
- hook: "<their opening line, verbatim>"
- structure: <the beats of the video, e.g. hook → problem → 3 tips → CTA>
- phrases: "<recurring or distinctive phrase>", "<another>"
- tics: <verbal habits: fillers, catchphrases, how they address the viewer>
- closer: "<their last line or call to action, verbatim>"
```

Field rules:
- **content_type**: `promo` when the video mainly sells something (their course, merch, an app
  launch). `review` covers a product review. Otherwise pick the closest of the rest.
- **sponsored**: `true` only when the transcript or description explicitly says so (a sponsor
  read, "paid partnership", `#ad`, an affiliate code). Put that mention after the value as a
  comment. Reviewing a product, or a brand sending it, is not sponsorship. Leave the sponsor
  read's own pitch out of `## Claims`.
- **topics**: reuse an existing tag when it fits, rather than inventing a near-synonym. Prefer
  a subject over a format: `hook-writing`, not `tips`.
- `## Claims` is required, even if it holds only one line. If the video truly makes no claim
  (a skit, a vlog), write `- none: <what the video is instead>`.
- **Voice** matters for every video, including promo: hooks and structure are how they talk,
  whatever the content.
