# Dispatch — 直修收弧修复轮（executor → Kimi）

依据: `69-review-direct-fix-gpt5.6-sol.md`（REWORK F1-F3 + fix prompt）与
`68-review-direct-fix-fable5.md` Addendum（Fable5 复核证实 F1/F2；F3 处置经用户拍板
取 **(a) 登记 known_red**，否决补造 stage-delivery 全套文件）。被审指纹（修复前弧）:
`96f5b441…:ee0b0a03…`。硬边界不变: 零 push、不改历史 review 原文/指纹、不扩 D-i 白名单、
不改产品行为；模板仓改动仅限 `validate-all-stages.py`（+其回归测试）。

## 第 0 步
提交本 stage 未跟踪的 68-/69- 两份评审落档（68 含 Addendum、69 含 .verdict.json）——
既是 RC9 落档义务，也让后续 validator 实跑有干净树。

## F1 — fixture compare 升级〔模板仓改 → merge 规则下行本仓〕
`scripts/validate-all-stages.py` compare 必须比较三样：`verdict` + **完整错误多重集** +
归一化 `applied_exceptions`；任一未登记变化 → 逐类打印明确 drift 行 + **非零退出**
（现在连 verdict FLIP 都退出 0，一并修）。交付可复跑的 sentinel 回归测试（对基线注入
仅-错误变化、仅-例外变化各一例，证明两者都被捕获、退出非零），测试输出留档
`72-compare-sentinel-tests.txt`。两仓脚本保持逐字节一致（模板仓先改，cp 下行）。
升级后基线语义变宽：重跑比对时若已红 stage 暴露 D3-v2 引起的错误集变化（如链式错误
消失），逐条登记进 64 迁移表，不许静默。

## F2 — bookticker 例外证据改指真原文〔本仓 main〕
1. 向 `09-user-authorization.md` **追加**本轮用户拍板原文（F3 处置 "a" 消息）并提交；
2. bookticker `status.json.authorized_exceptions[0]`：`evidence_file` 改指
   `reports/agent-runs/2026-07-red-gate-greening-v1/09-user-authorization.md`（已提交
   blob，含用户 verbatim 授权链：直修派工全文含 T3 + 执行确认 + 本轮拍板）；重算
   `evidence_sha256`；`reason` 改述为双源：09 封印原文 + 本 status.json
   `user_acceptance.instruction` 的 2026-07-15 历史豁免原文（记录自身携带，非封印源）；
3. 干净 main 上复跑 `validate-stage.py … --phase pre-accept`，新输出追加
   `62-bookticker-preaccept-green.txt`（append，不改写旧段）。
禁止改 `review_*`/tasks/指纹/70-handoff（历史 blob 一律不动——转述文本留在原处没错，
错的只是拿它当封印源）。

## F3(a) — 本 stage 登记 known_red + 最小账面补齐〔本仓 main〕
1. `64-fixture-migration-table.md` 补一行：`red-gate-greening-v1 = known_red`，理由=
   直修模式账本（真实产物 06/07/08/60-69 + 双评审 68/69），非 stage-delivery 运行记录，
   不补造 10-design/11-adr/20-implementation 等形态文件（用户拍板 a）；
2. 本 stage `status.json` 补 `session_receipts`（kimi 实现、fable5 与 gpt5.6-sol 评审、
   capture 归属；session id 查无则按惯例写 unavailable+原因+原始输出路径，禁止编造）；
3. `60-execution-log.md` 补完整页脚（Session ID 三件套 + 北京时间 + 下一步）。

## 收尾验证（全部在 committed HEAD 上，命令+原始输出进 40-fix-report.md）
`python3 -m py_compile scripts/validate-stage.py scripts/validate-all-stages.py`（两仓）；
A1-A8 driver 重跑 16/16；两仓 validate-all-stages 全量 + 升级版 compare 对更新后基线/
迁移表 → **零未登记 drift、退出 0**（并演示 sentinel 注入退出非零）；bookticker
pre-accept PASS-with-exception；`pytest backend/tests -q`（375）；
`node frontend/self-check.js`（80）；两仓 `git diff --check`。
`40-fix-report.md` 逐项映射 F1-F3 → 修复 + before/after + 新弧 head/指纹（重算）+
两仓状态 + 零 push 声明。完成即停，交 Fable5 + gpt5.6-sol 重审。

---
打包人: Fable 5（anthropic/claude-fable-5）
本地北京时间: 2026-07-18 01:35
下一步模型: kimi（修复）→ fable5 + gpt5.6-sol（重审 raw diff + 新证据）→ human（终审+push）
