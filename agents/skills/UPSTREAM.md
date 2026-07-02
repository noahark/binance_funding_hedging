# Skill Sources

Agency skill files in this directory are vendored from:

```text
repository: https://github.com/msitarzewski/agency-agents
pinned_commit: fc5a192e7e0f2fad0d74686d9165435e410869a8
license: MIT
```

Vendored files have been adapted for this Harness:

- Upstream Identity & Memory sections were removed.
- Project Harness Overrides were added at the top of each file.
- Reviewer skills are explicitly read-only and must end with schema-valid JSON.

Local skills are project-owned and have `source: local` in
`agents/registry.yaml`.

Do not refresh vendored files without updating `pinned_commit`, reviewing the
diff, and preserving the project overrides.
