---
name: skillify
description: Turn a creator's whole ingested output into one agent skill built from what they actually say, covering their methods and frameworks, their voice for writing scripts the way they talk, or both. Use when the user wants a skill, playbook or style guide from a creator who has been ingested. Usage: skillify <slug> [knowledge|voice|both] [--enrich] [install to <path>].
---

# Skillify a creator

Input: a creator slug, optionally with `--enrich`. The result is a standard Agent Skill folder
(SKILL.md plus references/) that works in any agent that reads skills.

**Stay faithful.** Everything in the skill comes from the creator's notes and transcripts. Don't
add generic advice, fill gaps with best practice, or "improve" their methods. Web research
happens only with `--enrich`, and its results go in separately labelled sections.

## Before you start

Find the `creator-skill` command and use it for every command below:
1. Inside the skillify repo: `.venv/bin/creator-skill` (Windows: `.venv\Scripts\creator-skill.exe`).
2. Otherwise `creator-skill` on the PATH, or `~/.local/bin/creator-skill`.
3. Neither works: install it with the `start` skill (one command), then come back.

Creator data lives in `creators/` under the current folder.

## Read the arguments

| The user wrote | Means |
|---|---|
| `ana` | creator slug (if none is given and only one creator exists, use it) |
| `knowledge`, `voice` or `both` | the mode: skip that question |
| `--enrich` (or "with web research") | do step 6 |
| `install to ~/.claude/skills` or a path | the install destination: skip that question |
| `all topics` | include every topic cluster without asking |

Ask only for what wasn't given, all together in one message (mode, topics, install location).

## 0. Preconditions

```bash
creator-skill stats <slug>
creator-skill notes-todo <slug>
```

If `remaining` is above 0, finish the notes first (stage 2 of the `ingest` skill), or ask the
user whether to go ahead with partial notes.

## 1. Ask

1. **Mode**:
   - **knowledge**: their methods, frameworks and rules of thumb
   - **voice**: write scripts and posts the way they talk
   - **both**
2. **Topics**: run `creator-skill topics <slug>`. Merge synonymous or overlapping tags into 3–15
   clusters (e.g. `hooks` + `hook-writing` + `openers` → *Hooks*), and drop tags with only promo
   videos. Show the clusters with their video counts and let the user pick (all by default).
3. **Skill name**: suggest one that says what it does, e.g. `<slug>-video-strategy` (knowledge)
   or `<slug>-voice` (voice). Lowercase and hyphens only.

Work in `creators/<slug>/skill/<skill-name>/`.

## 2. Topic files (knowledge or both)

For each cluster:

```bash
creator-skill topics <slug> --tags tag-a,tag-b,tag-c
```

That lists the cluster's videos (key, date, views, content type, promo and sponsored flags, note path), newest
first. Read those notes, and only check a transcript when you need a quote's context. Write
`references/topics/<cluster>.md`:

```markdown
# <Cluster title>

<2-3 sentences: what <Name> teaches about this and how central it is (N videos).>

## Principles
1. **<Principle in their terms>.** <One or two sentences in plain words.> "<short quote>" [key1, key2]

## Methods
### <Named framework or process>
1. <step, in their order> ...
[keys]

## Examples
- <their concrete example, briefly> [key]

## Numbers and tools
- <figure or tool + what they say about it> [key]

## Do / don't
- Do: ... [key]
- Don't: ... [key]

## Changed over time
- As of <newer date>: <current view> [key]. Previously (<older date>): <old view> [key].
```

Ranking and judgement:
- Order principles by how many **different** videos repeat them, then by those videos'
  combined views (`views_total`). Something said once in a low-view video goes last, or is cut.
- Promo videos (`promo: true`) don't add support on their own. Keep a claim from them only if
  non-promo videos back it. A sponsored video counts normally, but a claim about its sponsor
  needs backing from unsponsored videos.
- Contradictions: the newer view wins in Principles. Record the change under
  *Changed over time*.
- Cite the video keys for every point, as `[key]` or `[key1, key2]`.

If you can run sub-agents, give each cluster to one (at most 4 in parallel), with the rules above
and the slug. Have each return a summary of 10 lines or fewer: its top principles with keys. Then
write SKILL.md from those summaries without rereading every file.

## 3. Voice file (voice or both)

Inputs:
- the `## Voice` sections of all notes
- 5–10 full transcripts, mixing the most viewed and the newest, from several platforms and
  both short and long videos

Write `references/voice.md`:
- **Hooks**: their recurring opening patterns. Name each pattern, then give 2–3 verbatim
  examples [key].
- **Structures**: beat-by-beat templates for their common formats (e.g. 45-second tip video,
  10-minute review), with rough timings.
- **Pacing and delivery**: sentence length, how fast they get to the point, how they move
  between points, how they handle the viewer ("you", "y'all").
- **Phrase bank**: distinctive phrases and verbal tics, verbatim, with how often they recur.
- **Closers and calls to action**: verbatim.
- **Never**: things they conspicuously avoid (e.g. no clickbait, never says "guys").
- **Example scripts**: 2–3 new scripts on topics they cover, written in their style and
  labelled *"generated in the style of <Name>, not their words"*.

## 4. Sources

```bash
creator-skill sources <slug> --out creators/<slug>/skill/<skill-name>/references/sources.md
```

This lists every noted video with its date, views, type and the links on every platform.

## 5. SKILL.md

Write `creators/<slug>/skill/<skill-name>/SKILL.md`, under 400 lines:

```markdown
---
name: <skill-name>
description: <Name>'s <what it covers, specifically>, distilled from <N> of their videos (<platforms>, <date range>). Use when <the concrete situations to trigger it, in the user's words>.
---

# <Title>

<What this skill is, whose methods, how it was made, in 2-3 lines. Say it reflects <Name>'s own
statements up to <newest date>.>

## When to use
- <situation>

## Core principles
1. **<principle>.** <one line> [keys]   (the top 5-12 across all topics)

## Methods
<the 2-5 most important step-by-step methods, condensed; full detail in the topic files>

## Do / don't

## Voice in brief            (voice or both)
<3-5 lines + "see references/voice.md before writing any script">

## Examples
<2-4 short examples>

## References
- `references/topics/<cluster>.md`: <what's in it; when to load it>
- `references/voice.md`: <when to load it>
- `references/sources.md`: video links for every [key] cited
```

The description decides when the skill triggers, so make it specific: name the subjects and the
tasks (e.g. "writing TikTok hooks, planning a video series"). Avoid vague wording like "content
tips".

## 6. Enrich (only with `--enrich`)

For each topic file, research the methods it names on the web. Add a final section to that file:

```markdown
## External context (not <Name>'s words)
- <fact or counterpoint> ([source](url))
```

Never merge external material into their Principles or SKILL.md's core sections. In SKILL.md,
add one line under References saying that external context exists and where.

## 7. Check, install, report

```bash
creator-skill check <slug> creators/<slug>/skill/<skill-name>
```

Fix everything it reports: unknown keys mean an invented citation, so find the real video or cut
the point.

Ask where to install; more than one is fine:
- `~/.claude/skills/`: Claude Code, every project
- `~/.agents/skills/`: Codex and other agents that read the shared location, every project
- `<some project>/.agents/skills/` or `.claude/skills/`: one project only

Copy the whole folder: `cp -R creators/<slug>/skill/<skill-name> <destination>/`.

Report briefly:
- videos used (notes), per platform, and the date range
- top themes with their video counts
- what was excluded and why:
  - no speech or too short
  - promo videos, down-weighted, and sponsor reads
  - cross-posts merged
  - topics the user left out
- whether `--enrich` added external material
- the install path(s)
