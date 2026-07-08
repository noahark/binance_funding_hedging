# Review Output Naming

Each reviewer must write exactly one review file in this directory.

Use the reviewing model or provider name as the filename:

```text
<model-id>.md
```

Examples:

```text
claude-fable5.md
claude-opus4.8.md
glm52.md
kimi-for-coding.md
grok-build.md
gemini3.1pro.md
deepseek-v4.md
```

Do not overwrite another model's file.

Round / version suffix convention (the `-round2` suffix is already used and got
semantically mixed, so use version-specific suffixes going forward):

```text
<model-id>.md            # round 1 (original proposal / DRAFT-1)
<model-id>-draft2.md     # DRAFT-2 round  <- current
```

Current round: use `../review-prompt-v2.md` and write `<model-id>-draft2.md`.
Historical: `../review-prompt.md` was the round-1 prompt. Existing
`*-round2.md` files are prior artifacts (mixed DRAFT-1/DRAFT-2) — do not
overwrite them.

本地北京时间: 2026-07-08 16:38:03 CST
下一步模型: external reviewers
下一步任务: Write model-specific review files in this directory.
