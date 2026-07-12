# 对照方案: main 合入后文档语义同步 — GLM-5.2 视角

Status: **independent counter-proposal for operator / cross-model reference** —
非 stage 落档，非 bookkeeper 状态写入，不含任何 model dispatch 执行动作。
仅供与 `2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`（Grok
bookkeeper 起草的原 packet）对照评审。

- 落档模型: `glm-5.2[1m]`
- provider_identity: `zhipu_glm`（非 Anthropic；经 Claude Code 的 `claude-glm`
  本地别名访问，对应 `agents/registry.yaml#adapters.claude_glm`）
- 角色: 对照评审模型（read-only 视角）。**不**是本 stage bookkeeper，**不**
  执行 implementation/review/fix dispatch，**不**写 `status.json`。
- 落档时间: 2026-07-12 15:29:05 CST
- 对应原 packet: `reports/follow-ups/2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`
- 评审对象 stage: `2026-07-auto-review-pipeline-v1`（`accepted`，已 fast-forward
  合入 `main`）

---

## 0. 我为什么单独落一份

原 packet 的**原则层我同意**：evidence verbatim、navigation first、banner over
rewrite、no runtime change。它对 C2/C3/C5/C6/C7 的核实我也复算无误。但它有两处
我不能直接 ACCEPT：

1. **它的 §0 重排了 `AGENTS.md` 的权威顺序**（省略 `agents/skills/*.md` 与
   `agents/developer-discipline.md` 两级，凭空把 `docs/auto-review-pipeline.md`
   提到第 7）。一份"修复语义冲突"的文档自己制造了与最高权威的语义冲突。
2. **它的 C1 inventory 已过时**（`reports/follow-ups/README.md` 当前已是
   "delivered on main"）。

所以我落一份对照，把我**自己**的同步方法论写清，供其他模型（Codex / Claude /
Grok / Kimi）参考比对。下面所有判断均基于我对仓库当前 `main` 状态的实测，不基于
原 packet 的转述。

---

## 1. 我的核心立场（四条，顺序即优先级）

### 1.1 任何 hygiene 文档不得重写 AGENTS.md authority order

权威顺序是 `AGENTS.md` 第 52–66 行的**单一定义**。后续文档只能**逐字引用**，
不能"据 AGENTS.md"再排一遍——一旦重排就会漂移（原 packet §0 即是活例证）。
`docs/auto-review-pipeline.md` 的 normative 地位来自 `AGENTS.md` 正文（line 360
"defined normatively in"）的**引用**，不需要、也不允许在 authority order 里
单独提级；它仍属第 10 级 `docs/*.md`。

### 1.2 机械校验优先于手工文档纪律（本项目最深刻的教训）

`2026-07-harness-mechanical-gates.md` 的统一主题是："凡靠 prompt/人纪律的边界
必漂移，凡机械校验的边界才稳。"原 packet 作者在 §0 手写 authority order 就漂移
了——这恰好证明：**手工同步一次是不够的，必须把"导航文档 vs 真实状态"接成可
重复运行的机械检查**，否则下次合并 stage 后又会复发。

因此我的方案在"修文档"之外，强制要求一个 lint 检查（见 §4 P2），把一致性变成
不变量，而不是一次性手工成果。

### 1.3 证据 verbatim 红线 + 三层分类

不同文件有不同处置边界，我按三层分：

| 层 | 文件 | 处置 |
|---|---|---|
| **导航层**（描述当前世界状态） | `reports/follow-ups/README.md`、`reports/agent-runs/STAGE_INDEX.md`、`docs/README.md` | 可直接改当前状态；改前必须与 `status.json` 实测对齐 |
| **证据层**（历史事实） | `history/raw/*`、`*.verdict.json`、`*.prompt.md`、`30-review-*.md`、`50-review-*.md`、`60-test-output.txt` | **verbatim 红线**：不改一个字节（trailing whitespace 也保留）|
| **设计外壳层**（被取代的设计） | `10-design.md`、`11-adr.md`、`*-design-note.md`、`*-review-fable5.md` | **仅 header banner**，正文不动 |

### 1.4 最小、可逆、不碰 runtime

这批 hygiene **不**改 `scripts/`、`schemas/`、`workflows/templates/`、
`agents/registry.yaml` 的运行时语义，**不** push `main`。只动 markdown 导航正文
+ 证据文件的 header banner。唯一需要新增代码的是 lint 脚本，但它是**新增**文件、
**只读**校验，不改任何既有运行时契约，且应作为独立小 stage 走流程（P2）。

---

## 2. AGENTS.md 权威顺序（逐字引用，我不重排）

> 以下完全是 `AGENTS.md` line 52–66 的原序，**不是我排的**，hygiene 文档无权改动：

1. `AGENTS.md` — repository-level agent rules and safety gates.
2. `workflows/templates/*.yaml` — executable workflow contracts.
3. `docs/parallel-development-mode.md` — optional parallel/embedded cross-check.
4. `schemas/*.schema.json` — machine-readable output contracts.
5. `agents/registry.yaml` — model, adapter, and skill routing.
6. `docs/model-adapters.md` — local CLI adapter commands.
7. `agents/skills/*.md` — role skill prompts and local overrides.
8. `agents/developer-discipline.md` — developer execution discipline.
9. `reports/agent-runs/<stage>/` — current stage facts and evidence.
10. `docs/*.md` — product, architecture, and design notes.

`docs/auto-review-pipeline.md` 落在第 10 级；其强制力来自第 1 级 `AGENTS.md` 的
正文引用，**而非** authority order 里的独立层级。

---

## 3. 逐项裁决（基于我对 `main` 的实测）

| ID | 我的实测结果 | 我的处置 | 与原 packet 差异 |
|---|---|---|---|
| **C1** `follow-ups/README.md` §auto-review | **当前已是 "delivered on main"**，已 link 合约、已标 Historical、已注册原 packet 自身（line 27–54） | **无实质动作**；仅在 hygiene 收尾记录里标注"已 delivered，C1 预设动作已被预消解" | 原 packet "S1 修复" 已无对象，需降级为"核对" |
| **C2** `STAGE_INDEX.md` 缺项 | 实测：auto-review-v1 与 funding-annualized-history-v1 **皆不在 index**；后者 status=`accepted`、`merged_back_to_main=true`(no-ff)。原 packet 写的 "funding-history" 是不准简称 | 加两行（用准确 stage id `2026-07-funding-annualized-history-v1`）+ 刷日期；**并配 lint 防复发** | 原 packet 命名需订正；我额外要求机械门 |
| **C3** `docs/README.md` 缺 auto-review | 实测：canonical paths（line 6–17）确无该文件 | 加一条 bullet：`docs/auto-review-pipeline.md` — auto-review normative contract | 一致 |
| **C4** mechanical-gates §4 | §4 含**两点**：(a) `codex.default_model=gpt-5.5` 过时 → 已被 registry `gpt-5.6-sol` 解决；(b) "Gemini 3.1 Pro future-candidate 应补 2026-07 事件记录" → **仍未解决** | 仅给 (a) 加 header "model 点已 resolved"；**(b) 拆出为独立 follow-up**，不随 §4 关闭 | 原 packet 把整 §4 标 resolved，会误关 (b) |
| **C5** `review-fable5.md` 残留 | 含 `grok-build`（line 44/45/171）+ wall-clock 双上限（line 82/155） | **仅 header historical banner**，正文 verbatim | 一致 |
| **C6** `10-design.md` / `11-adr.md` 残留 | 两文件大量 `grok-build`/`wall-clock`/`parallel tip`/`dual-dev`（10-design line 174–729、11-adr line 131–368），均被 16-serial + 19-model-routing 取代 | **仅 header supersede banner**（指向 16/19 + docs/auto-review-pipeline） | 一致；额外提醒：banner 只增 header，不改正文字节，不影响该 stage 已 frozen 的 base..head fingerprint |
| **C7** `status.json` reason "unaccepted pipeline" | 措辞 "unaccepted" 过时（stage 已 accepted），但 AGENTS.md "Bootstrap stages must not self-host" 是**无条件**规则，结论不变 | **跳过**（极低风险措辞）；若做，仅改 reason 串，不碰逻辑 | 原 packet 列 optional；我建议直接 skip |
| **L1–L4** | 历史证据 `gpt-5.5`/`grok-build`、parallel wall-clock 语义、`opus4.8` 短名、symlink 路径 | **全部 leave alone** | 一致 |

---

## 4. 我的执行批次（重新编排）

> 设计原则：**先机械可验证的导航修正，再 banner，最后才考虑需要走 stage 流程的
> 代码**。每批都可独立提交、独立回退。

### P0 — 导航层修正（纯 markdown，0 runtime 风险）

| 动作 | 文件 | 验证 |
|---|---|---|
| 加 auto-review bullet | `docs/README.md` | `docs/auto-review-pipeline.md` 确实存在 |
| 加两行 stage + 刷日期 2026-07-10 → 2026-07-12 | `reports/agent-runs/STAGE_INDEX.md` | 两 stage 的 `status.json` 均 `merged_back_to_main=true` |
| 核对（不改）delivered 描述 | `reports/follow-ups/README.md` | 已是 delivered，仅确认 |

P0 完成定义：三个导航文件描述的世界状态 == `status.json` 实测。

### P1 — 设计外壳 banner（仅 header 注入，正文 verbatim）

| 动作 | 文件 |
|---|---|
| supersede banner（指向 16-serial + 19-model-routing + docs/auto-review-pipeline） | `10-design.md`、`11-adr.md` |
| historical banner（pre-delivery 设计评审，body 可能含 stale model/wall-clock） | `review-fable5.md`、（可选）`design-note.md` |
| §4 model 点 resolved header（**仅 codex.default_model 点**） | `2026-07-harness-mechanical-gates.md` §4 顶部 |

P1 约束：banner 是 prepend 的 header 块；**不删、不改、不重排任何既有行**。

### P2 — 机械门（独立小 stage，需走 delivery 流程；out-of-this-pass）

把"导航 ↔ 真实状态"一致性接成可重复运行的 lint（新增只读脚本，不改既有运行时契约）：

1. **stage coverage**：`STAGE_INDEX.md` 必须覆盖所有
   `status.json` 中 `stage_branch.merged_back_to_main=true` 的 stage（缺即 FAIL）。
2. **docs map coverage**：`docs/README.md` 必须列出 `docs/` 下所有实际存在的
   `.md`（或至少列出被 `AGENTS.md`/`registry.yaml` 引用的合约文档）。
3. **model truth consistency**：被文档标注为 "current truth" 的 model 字段
   （如 `gpt-5.6-sol`、`grok-4.5`、`claude-fable-5`、`opus4.8`）必须与
   `agents/registry.yaml` 一致。
4. **authority order 引用守则**（可选，弱检查）：hygiene/stage 文档若出现
   "authority order … from AGENTS.md" 字样，校验其列举的顶层条目集合是否为
   AGENTS.md 第 52–66 行的子集——**防原 packet §0 那类漂移复发**。

P2 落地形式：扩展 `scripts/validate-stage.py` 或新建 `scripts/lint-docs-sync.py`，
接入既有 validator 调用点。**因涉及 `scripts/`，须作为独立 stage 立项**，不在本
hygiene pass 内执行；本 pass 只产出需求与检查项清单（即本节）。

### 明确不做（本 hygiene pass 范围外）

- 不改 `AGENTS.md` / `registry.yaml` / `schemas/` / `workflows/` / `scripts/` 的
  运行时语义。
- 不重写任何证据层文件（含 trailing whitespace）。
- 不改 auto serial-only 合约、不动 parallel/dual-dev 设计。
- 不 push `main`（本地提交由操作者决定）。
- 不碰 `40-operator-decision-table.md` 冻结证据。
- C7 reason 串：跳过。

---

## 5. 与原 packet 的差异汇总

| 维度 | 原 packet (Grok) | 本方案 (GLM-5.2) |
|---|---|---|
| §0 authority order | 重排，省 skills + developer-discipline，提级 auto-review-pipeline | **逐字引用 AGENTS.md，不重排** |
| C1 | S1 "修复" README | **降级为核对**（已 delivered，无对象）|
| C2 | 加行 + 刷日期 | 加行 + 刷日期 + **订正 stage id** + **配 lint** |
| C4 | 整 §4 标 resolved | **拆分**：model 点 resolved；Gemini future-candidate 点独立 follow-up |
| C7 | optional 修 reason | **skip** |
| 防复发机制 | 无（一次性手工修） | **P2 lint 把一致性变成不变量** |
| 批次 | S1–S9（含 out-of-band 混列） | P0/P1/P2 三批，代码与文档严格分层 |
| Grok review 角色 | 表述含混 "dev + review" | 限定：manual 非 review gate，仅 auto review-1 primary |

**两份一致之处**（我认可）：evidence verbatim、navigation first、banner over
rewrite、no runtime change、L1–L4 leave alone、10/11 banner、C3 加 bullet。

---

## 6. 给操作者 / 其他模型的建议

1. **先修原 packet 自身**（§0 改回逐字引用、C1 降级、C2 命名、C4 拆分），再执行
   任何文件改动——一份错误的 hygiene 指令比不修更危险。
2. P0 + P1 可作为一个 commit-sized 批次提交，**纯 markdown，无需走 stage review**。
3. P2（lint）必须走 stage 流程——它动 `scripts/`，按 `AGENTS.md` 应立项为独立
   小修订 stage（与 `2026-07-harness-mechanical-gates.md` 同主题，可合并立项）。
4. 若操作者只采纳一份，我的建议是：**navigation 修正取原 packet，authority order
   与防复发机制取本方案**——两者互补，不互斥。

---

本地北京时间: 2026-07-12 15:29:05 CST
下一步模型: 操作者（决定是否把本对照方案纳入对照评审，或直接据 P0/P1 执行）
下一步任务: 操作者裁定原 packet §0/C1/C2/C4 修订；批准后执行 P0（导航三文件）+ P1（banner），P2 另立 stage
