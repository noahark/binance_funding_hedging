# PASTE BODY: Task B Drawer DOM-Order Fix

You are the executor in the existing interactive Kimi session. Perform this
bounded frontend fix in the repository. Do not start another model terminal,
do not return a `-p` launch command, do not delegate, and do not commit; the
bookkeeper owns commits and stage state.

Read `AGENTS.md`, `00-task.md`, `10-design.md`,
`20-implementation-frontend.md`, and this prompt before editing.

## Blocking Finding

`frontend/index.html` places `#drawer-backdrop` and `#drawer` after the main
`<script>`, while the IIFE calls `document.getElementById(...)` and then
`bindEvents()` during script execution. In a real browser, the drawer elements
are therefore `null` and `els.drawerClose.addEventListener(...)` stops startup.
`frontend/self-check.js` currently masks this by pre-populating mock elements.

## Required Fix

1. Move the drawer backdrop and drawer markup before the main application
   `<script>` so all drawer element lookups succeed before `bindEvents()` runs.
   Preserve the drawer's DOM, IDs, roles, labels, close control, visual order,
   and existing interaction behavior.
2. Add a static regression assertion in `frontend/self-check.js` that the
   drawer markup appears before the application `<script>` in `index.html`.
   Existing mocked drawer interaction tests remain; the new assertion must
   protect the real-browser initialization order they cannot observe.
3. Do not change backend, schema, fixture semantics, canonical docs, Harness,
   stage status/handoff, or any file outside Task B's allowed frontend files.
4. Append a `Drawer DOM-order fix` subsection to
   `20-implementation-frontend.md` with the changed files and command results.

Run:

```bash
node frontend/self-check.js
git diff --check
```

Do not report completion until both commands pass or you record a specific
blocker. End the appended report section with the required local timestamp
footer.
