# Codex 参考方案：main 合入后的文档语义同步与证据归档

Status: **independent reference plan; not executed and not operator-approved**

Authoring role: Codex，作为独立审查与方案整理者。

Branch observed: `main`。

Related delivery stage: `2026-07-auto-review-pipeline-v1`。

Relationship to the Grok plan: this file is an independent alternative to
`2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`. It does not approve,
adopt, overwrite, or claim authorship of Grok's uncommitted archive changes.

## 1. 目标

这次整理不应追求让所有文档使用相同措辞。不同文档承担不同职责，历史材料也必须保留当时的真实语义。真正需要同步的是：

1. 现行入口必须把读者导航到当前有效合同；
2. 同一项运行期事实只能有一个主真相源；
3. 镜像或说明文档不得与主真相源冲突；
4. 已验收证据和历史原文保持原样；
5. 后续模型能快速判断一份文档是“当前有效”“被取代”还是“仅作历史证据”；
6. 归档动作必须有独立、真实的 Git 提交身份，不得借用旧 checkpoint 的 SHA。

因此，本方案采用“按文档职责分层、按事实主源同步、按提交批次收口”，而不是全仓库搜索替换。

## 2. 冲突裁定顺序

发生语义冲突时，严格使用 `AGENTS.md` 中的完整权威顺序：

1. `AGENTS.md`
2. `workflows/templates/*.yaml`
3. `docs/parallel-development-mode.md`
4. `schemas/*.schema.json`
5. `agents/registry.yaml`
6. `docs/model-adapters.md`
7. `agents/skills/*.md`
8. `agents/developer-discipline.md`
9. `reports/agent-runs/<stage>/` 中的当前 stage 事实与证据
10. 其他 `docs/*.md`

`docs/auto-review-pipeline.md` 是 auto 模式的规范性说明，但它仍位于上述 `docs/*.md` 层级。它的细节必须与更高层的 `AGENTS.md`、workflow、schema 和 registry 一致，不能在冲突时自行提升优先级。

## 3. 文档语义分层

### A. 现行权威合同

示例：`AGENTS.md`、workflow YAML、schema、registry。

处理方式：

- 直接修正当前有效语义；
- 同一变更批次中同步必要的验证器与测试；
- 不通过历史文档反向定义运行期合同；
- 合同变更与纯文档卫生分开提交。

### B. 现行说明与命令手册

示例：`docs/auto-review-pipeline.md`、`docs/model-adapters.md`。

处理方式：

- 跟随更高权威层同步；
- 说明“为什么”和“如何使用”，不复制可机器读取的完整配置；
- 模型 ID、超时等易漂移值尽量引用 registry 的字段路径；
- 命令形态保留在 adapter 手册或 runner，不散落到任务文档。

### C. 导航与状态索引

示例：`docs/README.md`、`reports/follow-ups/README.md`、
`reports/agent-runs/STAGE_INDEX.md`。

处理方式：

- 允许更新为当前事实；
- 明确标注 `active`、`delivered`、`superseded`、`historical-reference`、`open-follow-up`；
- 只承担导航，不重新讲一套运行期合同；
- stage 状态从各 stage 的 `status.json` 派生，不能凭叙述猜测。

### D. Stage 当前状态文件

示例：`status.json`、`70-handoff.md`、`current_inputs`。

处理方式：

- 它们是该 stage 的当前机器/人工交接事实，可以为归档操作做机械更新；
- 更新前保留快照；
- 不重写已经发生的历史理由；
- 新事件新增独立记录，不把旧 checkpoint 改名成新事件；
- 所有 commit 字段只能绑定实际承载对应内容的提交。

### E. 已验收设计、评审、判决和原始证据

示例：stage 的 `10-design.md`、`11-adr.md`、review verdict、prompt、原始输出和测试日志。

处理方式：

- 原文不可因后续语义变化而改写；
- 不在已被 review 的正文上补“当前语义”横幅；
- 被取代关系写入外部导航索引或新的 operator decision；
- 移入 `history/` 时保持字节不变，并用兼容 symlink 保持旧路径可访问。

### F. 名称带 `draft`、但已成为冻结基线的文档

示例：`docs/phase2-direction-draft.md`、
`docs/private-account-v1-direction-draft.md`。

处理方式：

- 语义按引用关系和后续批准事实判断，不能只凭文件名判断；
- 已被多个验收 stage 引用为基线时，保留原路径和原文；
- 若要重命名，必须单独做引用迁移和兼容性评估，不放进本次卫生整理。

### G. 尚未提交的整理操作

当前工作树中的 Pass B archive 属于这一层。

处理方式：

- 可以验证为“文件系统层面已执行”；
- 在提交前不能描述成“已进入项目历史”或“已由某 SHA 承载”；
- 必须与已经合入 main 的产品/Harness 交付事实分开表述。

## 4. 每类事实的唯一主真相源

| 事实 | 主真相源 | 其他文档的职责 |
|---|---|---|
| 仓库级角色、安全门、授权边界 | `AGENTS.md` | 只引用，不另造例外 |
| Stage 状态机与路由意图 | workflow YAML | 文档解释流程，validator 落实约束 |
| auto 授权、receipt、verdict 数据形状 | schema | 手写 validator 与测试必须同语义 |
| 模型、provider、adapter、timeout 值 | `agents/registry.yaml` | adapter 手册说明实际调用方法 |
| CLI 与 shell 调用形态 | `docs/model-adapters.md` 和 runner | 任务 prompt 不复制启动命令 |
| auto review 细节 | `docs/auto-review-pipeline.md` | 不得覆盖上层合同 |
| 单个 stage 的当前状态 | `status.json` | `70-handoff.md` 提供人类可读镜像 |
| 已发生的历史决策 | 原始 decision/review/evidence | 索引只标注其历史地位 |

同步原则是“修改主源，再检查镜像”，而不是让所有文件彼此互相复制。

## 5. 我会如何拆分实际执行

### Batch A1：只提交 Pass B 的归档内容

范围：

- 20 个根目录历史文件转换为兼容 symlink；
- 对应的 `history/raw/` 原始文件；
- 两个归档前快照；
- `history/README.md` 的归档索引。

要求：

- 20 个旧路径经 symlink 读取的字节必须与归档前 `HEAD` 相同；
- `history/raw/` 文件不得做内容改写；
- 不在这个提交中声称已知自身 SHA；
- 若 `status.json` 必须随 A1 更新，只能记录 `pending_content_commit` 或不填 commit，不能填旧的 `433980d...`；
- 保留原 `bookkeeper_checkpoint` 的名称、意义和原始 SHA。

### Batch A2：绑定真实归档提交并收口状态

A1 提交完成后才能执行：

- 在 `status.json` 增加独立记录，例如
  `history_archive.post_accept_archive.content_commit`；
- 该字段绑定 A1 的真实提交 SHA；
- 同步 `70-handoff.md` 的归档状态；
- 保留旧 checkpoint，不把旧 checkpoint 重命名为归档事件；
- 在 clean `main` 上运行 stage checkpoint/pre-accept 验证。

A1/A2 分拆的原因是避免提交自引用，也避免一个旧 SHA 被赋予实际上没有承载的内容。

### Batch B：只修导航语义

建议只改以下入口：

1. `reports/follow-ups/README.md`
   - 将 auto-review v1 标为 delivered/merged；
   - 将早期 design note 和 Fable5 review 标为 historical-reference；
   - 标记 mechanical-gates §4 已被模型路由收敛解决，§1–3、§5 仍是独立 follow-up。
2. `reports/agent-runs/STAGE_INDEX.md`
   - 从 stage `status.json` 补入 auto-review v1；
   - 补入 funding annualized history stage；
   - 将无 `status.json` 的 design-review 目录标为 historical-reference，而非伪装成标准 stage。
3. `docs/README.md`
   - 增加 `docs/auto-review-pipeline.md` 的入口和适用范围。

这批不改运行期、schema、registry、validator、测试，也不改 accepted stage 的设计正文。

### Batch C：另行处理真正的合同冲突

如果扫描发现活跃合同层仍有冲突，则单独开一个明确授权的小型 Harness 任务。它不与 A/B 的证据归档和导航修改混合。

候选事项包括：

- 验证 `claude-glm` 在 auto runner 的真实 `/bin/sh`/login shell 上下文中是否可解析和执行；
- 若需要，修正 adapter 入口，而不是因其他终端曾调用成功就推定 runner 一定成功；
- 正式定义 Harness Fast 的适用条件、允许文件、验证门和禁止项；或者明确本次只是一次 operator-authorized 的 main 文档卫生例外；
- mechanical-gates §1–3、§5 若要实现，作为独立开发与 review 工作。

## 6. 明确不做的修改

本次语义同步不应：

- 修改已验收 stage 的 `10-design.md`、`11-adr.md` 正文或添加新横幅；
- 移动或改写两个已经作为冻结基线使用的 `docs/*-direction-draft.md`；
- 批量替换历史 prompt、review、verdict 中的旧模型名或旧 wall-clock 设计；
- 修改 `status.json` 中当时真实的 bootstrap/non-self-hosting 理由；
- 把导航不一致标成 P0/P1 运行期故障；
- 在文档卫生批次里顺带调整 runner、registry、schema 或产品代码；
- push、发布或执行模型分发。

## 7. 风险与优先级表达

文档卫生不使用代码缺陷的 P0–P3 等级，以免把“导航过期”和“运行期 fail-open”混为一谈。建议使用：

- `active-contract-conflict`：活跃权威层之间冲突，必须先处理；
- `navigation-stale`：入口指向旧状态，应在本批修正；
- `historical-wording`：历史原文与现行合同不同，但应保留；
- `path-compatibility-risk`：移动会影响引用，需要单独迁移；
- `out-of-band-runtime-check`：需要真实 adapter/runner 验证，不属于文档卫生。

## 8. 验收检查

### A1/A2 归档检查

```text
20 个归档文件逐一与归档前 HEAD 做 byte-equality 检查
stage 根目录 broken symlink = 0
status.json.current_inputs 中每个路径都存在
python3 -m json.tool <stage>/status.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase pre-accept
git diff --check
```

还要人工确认：

- A1 的真实 SHA 被 A2 正确引用；
- 原 `bookkeeper_checkpoint` 未被改名或重新解释；
- `history/README.md` 能区分早期 slimming 和 post-accept archive 两次动作；
- Git diff 中没有历史文件内容变化，只有路径类型和索引/状态的机械变化。

### B 导航检查

```text
git diff --name-only <batch-base>..<batch-head>
git diff --check <batch-base>..<batch-head>
```

并确认：

- 变更文件严格限制在三个导航入口；
- `STAGE_INDEX.md` 的 accepted/merged 信息可由对应 `status.json` 复核；
- 活跃导航中不再称 auto-review v1 “尚未交付”；
- 历史材料只在索引中标记，不改正文；
- 没有产品路径、运行期脚本、schema、registry 或 accepted evidence 变化。

### C 活跃语义扫描

扫描时应排除 `history/`、原始 evidence 和冻结基线，避免把预期存在的旧术语当成残留。扫描结果应按第 7 节分类，而不是以字符串命中直接判定缺陷。

## 9. 供其他模型评审的问题

请评审模型重点回答：

1. 是否同意按 A–G 文档职责分层，而不是统一改写措辞？
2. A1/A2 是否足以解决 archive commit 自引用和旧 SHA 错绑问题？
3. 是否有任何一个 Pass B 文件必须继续作为 stage 根目录真实文件，而不能是兼容 symlink？
4. Batch B 的三个导航入口是否足够，是否遗漏其他活跃 startup 入口？
5. 哪些问题属于 `active-contract-conflict`，必须从文档卫生中拆出单独修复？
6. 是否发现本方案误把冻结基线当历史材料，或误把历史证据当现行合同？

建议输出：

- `ACCEPT`
- `ACCEPT_WITH_AMENDMENTS`，逐项列明修改
- `REWORK`，只列阻塞问题与证据路径

## 10. 当前落档边界

本文件只记录 Codex 的建议做法。落档本身不代表：

- 接受 Grok 已执行的工作树变更；
- 授权提交 A1/A2/B；
- 变更已验收 stage 的状态；
- 认可任何尚未验证的 adapter 可用性；
- 授权 push 或模型分发。

```text
本地北京时间: 2026-07-12 15:28:28 CST
下一步模型: 其他独立评审模型
下一步任务: 对本方案的分层、A1/A2 提交边界与 Batch B 导航范围进行对照评审
```
