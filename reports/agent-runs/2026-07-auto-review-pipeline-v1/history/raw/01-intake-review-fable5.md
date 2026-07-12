# Intake Review: 2026-07-auto-review-pipeline-v1 (Fable5)

Status: **INTAKE REVIEW — ACCEPT-with-edits（2 处记录级修补，不阻塞进入 stage-design）**
Date: 2026-07-11
Reviewer: Claude Fable 5 (anthropic/claude-fable-5)
Reviewed artifacts: `00-intake.md` / `status.json` / `70-handoff.md` /
`60-test-output.txt`（H_intake 9573d2a + checkpoint 030dd28）
独立复核项：H_intake 提交内容（`git show --stat`）、stage 分支来源
（main 45c21ee）、冻结源 commit（docs 分支 tip 1997a65 与 status.json 一致）、
冻结 40 表中双评审 patch 的实际落点（非转述核对）。

## 1. Verdict

**ACCEPT-with-edits。** Intake 机械面与语义面均合格，可进入 stage-design；
两处记录级修补建议在 designer 动笔前顺手完成。

## 2. 核对通过项

- **分支与提交机械面**：`stage/<id>` 自 main 45c21ee 建出，H_intake 单提交
  导入完整设计链（30/31/40/41/42/43 + note + 首轮评审 + README 索引 +
  intake 四件套），无任何产品路径；`--phase checkpoint` PASS 有档；
  拒绝前缀清单与 61 处 imported-evidence trailing-whitespace 的处置
  （冻结证据不重写、delivery diff 以 H_intake 为 base 独立过
  `git diff --check`）均正当，后者与 metal-v1 残差 R3 的既有处置先例一致。
- **冻结基线真实性**：status.json 宣称的 source commit 1997a65 == docs
  分支 tip（已验）；40 表确已含 F1–F3 与 G1–G6 全部合并结果——D7 的
  tip-once 空集修复、bind 的 byte-equality capture/assert 语义、§C
  `invalid_json_max_attempts_per_model: 2` 回对齐、P13 威胁边界，
  与 `43-decision-table-patch-merge.md` 的 merge matrix 逐项相符。
- **冻结目标与 40 表一致**：intake 九条冻结目标对 D1/D2/D4/D7/P6/P7 的
  转写准确（含 G3 修补后的"code-changing retries 合计 ≤2"表述）；
  非目标区正确锁定 fingerprint 零改动、v1 不动 verdict schema、
  不自举 auto pipeline（bootstrap 悖论处理正确且显式）。
- **路由诚实性**：Codex 排除于 core work；bookkeeper 披露完整；
  direction panel 跳过以"已冻结多模型综合 + 操作者显式指令"为据，
  符合 HIGH 的 user-override 路径；`open_design_items` 与我在 41 号
  评审留下的两个非阻塞形状项（authorization artifact、mode-flip 字段）
  以及 P8/评审单元/路径/拓扑/路由完整对应，无遗漏。

## 3. Minimal edits（2 处，记录级）

1. **[status.json] review_1/review_2 的 `reviewer_prior_involvement` 预填
   `"none"` 与 intake 自己的警告矛盾。** Intake 人工门一节明言两家高端
   provider 均参与方向链、"不能伪装成 none"，但占位块已把 "none" 写死——
   这是日后忘改即静默穿门的典型伏笔（本 stage 的主旨恰是消灭这类伏笔）。
   建议改为 `null`（与 reviewer/provider 同为未定态），或加
   `"_pending_selection": true` 类标记；选定 reviewer 时按真实参与度填
   `direction_synthesis`/`design`。注意事实：GPT 与我的 patch 已被合并进
   冻结 40 表正文，两家的参与不是"评过"而是"内容进了综合"，review-2
   无论选谁都必然走 strong-reviewer disclosure override，或启用 registry
   已预留的第三决策模型（`future_review_2_fallback_candidates:
   Gemini 3.1 Pro`，其触发条件"design-conflict override 频发或用户明确
   批准"正是本 stage 情形）——建议 stage design 把这两条路线并列给
   操作者选。
2. **[00-intake.md] complexity evaluator 路由偏差缺一行理由。**
   模板 `rotation.complexity_evaluator` 是 claude_glm/glm-5.2，本次由
   Codex bookkeeper session 完成分类。分类结论 HIGH 无争议（与双评审
   建议一致），但按纪律应补一行偏差说明（例如：分类实质由操作者指令 +
   双模型评审链预先确定，GLM 独立分类不增加信息、且会多一次人工
   dispatch）。诚实记录偏差，而不是让它看起来像默认路由。

## 4. 非阻塞备注

- `lightweight_skip_allowed: true` 的旗名易误读（HIGH 无 lightweight
  概念），intake 已附中文澄清，stage design 定 opt-in 字段时避免复用
  该措辞即可。
- bookkeeper model 记为 "current Codex/GPT session"，作簿记身份可接受；
  若该 session 后续出具任何 gate 级产物，需补确切 model id。

## 5. 结论

Intake 如实转写了冻结决策表、边界干净、bootstrap 不自举、开放项清单
完整。完成上述两处修补后，designer 可依 40 表起草
`00-task.md` / `10-design.md` / `11-adr.md`；本评审不授权实现或 dispatch。

```text
本地北京时间: 2026-07-11 11:40:13 CST
下一步模型: Codex/GPT（stage designer；先落两处 intake 修补）
下一步任务: 修补 status.json 预填值与 evaluator 偏差说明 → 起草 00-task/10-design/11-adr → HIGH 必需的 development breakdown
```
