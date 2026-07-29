# Developer Discipline

This file is the developer execution discipline for implementation and fix work.
It applies to every implementation-capable model, including Claude-GLM, Kimi,
and Grok or another non-Codex model when explicitly enabled for implementation
or fix work.

In this repository, `AGENTS.md`, the valid dispatch packet, current
`status.json`, and task acceptance criteria have higher authority.

Source note: adapted from the widely used `CLAUDE.md` guidance in
`multica-ai/andrej-karpathy-skills`.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with
project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial
tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes,
simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it
work") require constant clarification.

## 5. Reading Discipline

**Read the relevant raw evidence once, then return by anchor.**

Packet scopes reduce unnecessary corpus size; this section separately prevents
the session from spending that saved budget on repeated reads or bulk output.

- Do not re-read a whole file you have already inspected; return to the needed
  line range or named function instead.
- Keep searches narrow and retain only the result lines needed for the task;
  do not flood context with whole-file or bulk-search output.
- If you materially exceed the packet's stated reading budget, stop and report
  to the bookkeeper before continuing. Context exhaustion can trigger
  compaction mid-implementation and lose frozen constraints; this repository
  has previously found cross-seam drift after that failure mode.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer
rewrites due to overcomplication, and clarifying questions come before
implementation rather than after mistakes.
