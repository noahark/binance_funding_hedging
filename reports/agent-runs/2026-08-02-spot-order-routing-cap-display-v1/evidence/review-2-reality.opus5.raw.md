# review-2-reality — Opus5 原始回执

由 Human 于 2026-08-03 交回 Bookkeeper；原文中的正式回执与返工要求保留如下。

```text
以 Opus5（anthropic）、全新只读会话，对固定区间 1a55781..3a07f4a 完成了 HIGH_RISK review-2。披露：我参与过本 stage 的方案整合与前后端任务拆分，因此下面每一条都以固定区间的代码、测试与实际运行结果为准，不复述我自己的规划文字。

先说结论

功能本身做对了，但这份交付把仓库的全量测试跑成了红灯，而且红掉的正是守着"allowlist 不许悄悄变大"的那个测试。结论：REWORK（返工）。

F1 · 全量测试红灯，且红的是 allowlist 守卫 —— in-range，阻塞

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
→ 2 failed, 1213 passed

FAILED backend/tests/test_hedge_purity.py::test_allowlist_is_exactly_the_frozen_seven_endpoints
FAILED backend/tests/test_hedge_purity.py::test_allowlist_hosts_all_hardcoded_papi

这两个测试是冻结 allowlist 的守卫：一个断言允许调用的接口恰好是那 7 条，一个断言每条的域名都硬编码成 papi.binance.com。本轮经 Human 授权新增了 5 条 api.binance.com 的接口，守卫没跟着更新。新加的测试只断言这五条在里面，没有断言没有第六条。

根因是同一个家族的第二次发作：这次交付改了共享的常量和函数签名，凡是在 dispatch 手挑的那份测试清单之外的既有测试就都失效了。上一轮已经修过两份回归测试，但验收命令仍是手挑的 14 个文件，没有穷举。

F2 · 安全不变量的文档已经失真 —— in-range

backend/services/hedge_open_live_client.py 模块开头仍写着：「Default-off (ADR-4)：只有 APP_HEDGE_EXECUTOR=live 且凭证齐全时才会构造实例；disabled/record 模式下不存在实例」。本轮 backend/app/server.py 的 _build_restricted_asset_client 正是在与 APP_HEDGE_EXECUTOR 无关的条件下构造了一个实例。该段接口清单也仍只有 7 条。

F3 · 契约的权威指向反了 —— in-range，低

契约 v0.9 段写「Authority order: 接口约定 > 本节」，但接口约定第 0 节自己写明它不是对外权威。F3 可改可不改，不阻塞；不改就记为后续项。

修复要求

1. 修 backend/tests/test_hedge_purity.py：_FROZEN_ALLOWLIST 更新为本轮已授权的 12 条（7 条 PAPI + 5 条 api.binance.com），长度断言改 12；host 断言改为按域名分组（PAPI 七条 → papi.binance.com，新五条 → api.binance.com），保留“域名全部硬编码、调用方不可传入”的原意。禁止用删断言、改成子集包含、或回退生产 ALLOWLIST 的方式让它变绿。
2. 穷举扫描：列出 backend/tests/** 中所有对本次改动过的共享常量/签名（ALLOWLIST、get_snapshot、query_leg、prepare_attempt、_persist_leg_raw、build_rows）做静态冻结或桩实现的测试，逐条给出“已修 / 无需修及理由”。
3. 验收命令换成全量：PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider 外加 node frontend/self-check.js，回执附原始尾行。
4. 同轮更正 F2：hedge_open_live_client.py 的 ADR-4 段落改为陈述现状（下单执行路径仍 default-off；展示路径由组合根按 §E-4 独立注入，只用于名单 GET），端点清单补齐五条。
5. F3 可改可不改，不阻塞；不改就记为后续项。
6. 修复范围应只限 backend/tests/test_hedge_purity.py 与 hedge_open_live_client.py 的 docstring，不得触碰生产逻辑、契约语义、schema、前端渲染或 Start gate。由原作者 claude_glm 执行，完成后按规则重跑 review-1（DeepSeek）。

[TASK_RESULT v2]
任务 ID: review-2-reality
执行结果: completed（完成）
结果摘要: HIGH_RISK review-2（Opus5，全新只读，已披露设计参与）完成。业务效果成立：正/负费率路由、普通现货闭环与 leg 行 endpoint 唯一权威、展示四态与缓存隔离、本轮非目标未突破，均经固定区间代码追踪与实跑验证。但按 DEVELOPMENT_GUIDE:115 规定的全量命令跑，交付处 2 failed / 1213 passed，红的是冻结 allowlist 的守卫测试，意味着 §E-2「不得绕过 deny-by-default」当前无自动检查在守；同根因（改共享常量/签名后，dispatch 手挑清单外的既有测试失效）已是第二次发作，全阶段无人跑过全量。评审结论 REWORK。
产物: [none（只读评审，未写入任何仓库文件）]
检查结果:
1. [pass] 固定区间核验：git rev-parse 两端均解析成功；git diff --check 1a55781..3a07f4a exit 0；HEAD 即 3a07f4a 且工作区无代码改动；区间 3 提交 / 26 文件。
2. [pass] 路由效果：decide_spot_route 三分支正确；负费率不读名单、不选 regular_spot；名单/现货账户/现货限频任一读取失败即 fail-closed，零 attempt 零 POST；余额不足与读取失败可区分。
3. [pass] 普通现货闭环与审计：leg 行 endpoint 由路由写入并成为查单与原始响应的唯一来源；无 sideEffectType；PRODUCT_SPOT 空码表使 51169 不被误判为抵押额度码，无自动补腿。
4. [pass] 展示四态与隔离：命中/未命中/失败即未知/无现货腿不适用；方向无关；预检每次新读；node frontend/self-check.js 全绿。
5. [pass] 非目标未突破：无 DB 迁移、backend/config.py 未改、无新环境变量、openLongRestrictedAsset 仅见于注释与测试数据、Start gate 未变。
6. [fail] 全量回归红灯（F1，in-range）：pytest backend/tests -q → 2 failed / 1213 passed，test_hedge_purity.py 的两个冻结守卫失效。
7. [fail] 证据充分性不足（F1 同源）：实现者、Bookkeeper 与两轮 review-1 全部只跑 dispatch 手挑的 12–14 文件子集；阶段内文档零处提及全量命令或该守卫文件。
8. [fail] 安全不变量文档失真（F2，in-range）：hedge_open_live_client.py docstring 仍称非 live 模式不存在该客户端实例，与本轮组合根注入矛盾；端点清单亦未补五条。F3 为低优先文档项。
阻塞项: [F1 全量回归红灯 + allowlist 守卫失效，须按修复要求 1–3 穷举修复并以全量命令验收；F2 须同轮更正]
评审结论: REWORK（返工）
问题记录: 本回执正文问题记录段（F1/F2/F3，均标为 in-range，无 pre-existing 主张故无需 base 前 blame 证据）
修复要求: 同一文件的修复要求第 1–6 条（穷举扫描 + 全量验收命令为硬性要求，禁止再以手挑子集验收）
本地北京时间: 2026-08-03 10:07:41 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本原始回执交回 Bookkeeper；Bookkeeper 封存本回执，current_task.state 保持 reported 不写 verified，按 §8 将 rework_count 由 1 递增为 2，并准备 claude_glm 修复 dispatch；修复提交后更新 delivery_sha 并重跑 DeepSeek review-1，再回 review-2。review-2 未 ACCEPT 前不授权合并、部署或实盘。
[/TASK_RESULT]
```
