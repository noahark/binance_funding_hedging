# Execution Log — red-gate-greening-v1 直修弧（executor: Kimi）

授权：`09-user-authorization.md`（用户派工 verbatim + "执行吧"）。
执行者： Kimi（moonshot_kimi，`kimi --model kimi-code/kimi-for-coding`）。
约束： 两仓全程零 push；不改历史 review 原文/指纹/产品行为；白名单不扩项（D-i 未拍）。
模板仓工作分支 `harness/d3-v2-direct`（本地合 main `d6cf9a3`）；本仓 stage 分支证据
ff 进 main 后，T5 起全部在 main 上提交。

## 第 0 步 — 证据入库（commit `b841540`，stage 分支）

- 新建 `09-user-authorization.md`（用户派工消息 verbatim + 执行放行）。
- `git add 06/07/08/09 + docs-truth-sync 82` 并提交（05 已跟踪；82 为 docs-truth-sync
  引用却从未入库的裁决文件，补齐）。

## T0 — Stage A 模板仓账本收口（模板仓 commit `681712c`）

- 实测矛盾真形：`status=stage_accepted_waiting_user` vs `stage_branch.merged_back_to_main:
  true`（嵌套字段，存在）+ `user_acceptance` 缺失 vs git 历史已有合并 `9ea36ab`/记账
  `cdef1ee`（派工包"merged_back_to_main:true"的字段位置描述不准，实质成立）。
- status→accepted、补 terminal_reason/next_action、新增 user_acceptance（合并+cp 事实；
  接受 verbatim 查无 → 如实登记证据缺口，不补造）；70-handoff 同步。

## T2a — Golden 基线（模板仓 commit `b4b4431`；本仓 commit `bf1991d`）

- 新建 `scripts/validate-all-stages.py`（147 行；import 同仓 validate-stage.py，
  记录级 pre-accept：跳过 clean-worktree 与 branch/recheck 上下文断言，排除 `_template/`）。
- 基线（v1 链式 validator）：funding_hedging **12 green / 11 red**；模板仓 1 green。
  落盘 `63-fixture-baseline-{funding,template}.{json,txt}`。
- `64-fixture-migration-table.md` 登记：4 个预期翻转、7 类维持红（含基线新发现的
  env-startup-v1、local-service-launchd-v1）、12+1 个不得翻转的绿。

## T1 — D3-v2 重写（模板仓 commit `878db79`；证据 commit `01e9432`）

- `validate_task_coverage()` 重写为路标模型（净 -113 行）：规则 1 前缀命中（全量 j=n
  为常态）+ 规则 3 class-1 例外（review_k 无命中则不担保任何东西——A8b 实证；
  task:<id> 盖 task.head 所在段，非路标则记录错误）。删除链式检查、
  `_task_own_review_covers`（dev 坐标冒充口子）、`covers_through_task`（0/23）。
- DoD：A1-A8 对抗用例 **16/16 PASS**（`61-adversarial-d3v2.{driver.py,txt}`；
  A7 用 bookticker 真实数据在 funding 仓内存模拟 + class-1 → green_with_exception）。
- 文档：模板仓 harness-design D3 段改 v2 + fixture 规则入文；Stage A 10-design §3/§5
  追加订正 note（不改写原文）；`_template/status.json` 加 `coverage_waypoints` 示例。
- `python3 -m py_compile scripts/validate-stage.py scripts/validate-all-stages.py` 通过。

## T2b — 基线复跑比对（commit `99d6cb4` → `65-fixture-t2b-compare.txt`）

- v2 validator 复跑：funding 15 green / 8 red；翻转恰为迁移表登记的 3 项
  （annualized-history、phase2-borrow-sort、private-account）；bookticker 如预期仍红
  （仅剩 review_1 尾随，例外 T3 才写入）；模板仓 no drift。

## T6 — 治理规则 + 台账（模板仓 commit `16db466`；本仓 commit `a05335d`）

- harness-design 新增 "Close-out Governance (Subordinate Rules)"（三条，标注从属于
  review-2 + 用户显式验收主线）与 "Known Issues Registry"。
- 本仓 `reports/follow-ups/2026-07-harness-known-issues-registry.md`（K1-K7）。

## T5 — 下行同步（本仓 main commit `ad8ad96`；前置 ff 合并 stage 分支证据）

- 模板仓 `harness/d3-v2-direct` 本地合 main（`d6cf9a3`）。
- 本仓：stage 分支 ff 进 main（证据随附）→ cp validate-stage.py /
  validate-all-stages.py / harness-design.md；`_template/status.json` 字段级 merge
  （只增 coverage_waypoints，保留 session_receipts + reporting_preferences）；
  AGENTS.md / model-adapters.md 未动；schema 本就一致无需同步。
- carve-out 校验留档 `66-t5-carveout-verification.txt`（5 项全过）。

## T3 — bookticker 真转绿（main commit `f322986` + 证据 `8c9cca6`）

- 追加 class-1 例外（scope=review_1、钉现指纹、evidence=已提交 70-handoff.md blob +
  sha256 封印、authorizer=user、reason 言明破印回红属设计行为）。仅向前追加。
- main 上实跑 pre-accept：**STAGE VALIDATION PASSED — PASS (1 authorized exceptions
  applied: review_fingerprint_trails_status@review_1)**（`62-bookticker-preaccept-green.txt`）。

## T4 — docs-truth-sync handoff 归一（main commit `40623e1`）

- 仅 70-handoff.md 正文对齐 accepted/merged/pushed 终态（status.json 早已归一，未动）；
  追加 K1 台账注记与"bookticker 真绿依赖本直修 T1+T3"note。

## T7 — prose 清欠（main commit `82e2ef5`，独立 commit）

- symbol-snapshot `:5`（mode-dependent 改写，非删句）+ refresh_status 描述、
  funding-history `funding_history` 描述、`snapshot_service.py` docstring same-version
  残句；连带删除合同两处 drift 披露注记（该文件无 "Residual Risks" 节，两处即全部，
  删除同时消除悬空引用）。
- 验证：schema diff 仅 description 行（非 description 变更行=0）；JSON 合法；
  backend pytest **375 passed**；frontend self-check **80 PASS**。

## 收口 — 终态复跑（commit `96f5b44` → `67-final-fixture-compare.txt`）

- funding_hedging：**15 green + 1 green_with_exception（bookticker）+ 7 red**（全部为
  迁移表登记的 known-red）；翻转恰为登记的 4 行；模板仓 no drift。**迁移表全集满足：
  无未登记的红、无未登记的翻转。**

## 交付物（两仓本地 commit，零 push）

- 模板仓 main `d6cf9a3`（含 T0/T2a/T1/T6）；本仓 main `96f5b44`（含第0步、T2a 基线、
  T1 证据、T2b、T5、T3、T4、T7、收口复跑）。
- 证据文件：09、61（driver+txt）、62、63（×4）、64、65、66、67。
- 停下等：Codex + Fable5 raw-diff 独立评审（输入 = 两仓 diff + 61/62 + 63/64/65/66/67）
  → 用户终审 → 统一 push。

---
执行者 Session ID: unavailable（Kimi CLI 未向模型暴露 provider-native id）
本地北京时间: 2026-07-18 00:50 CST
