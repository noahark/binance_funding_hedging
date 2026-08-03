非阻塞说明（不设修复要求）：① _build_hedge_service 的 mode != "live" 分支提前返回，backend-2 实现组合根注入时应在 run() 组装处（service = SnapshotService(config) 附近）独立构造只读 client，与 live executor 解耦——任务卡已明确该要求，非新问题；② 前端消费规则与 S1–S8 接缝不在本轮范围，留 review-1 显式核对（task-breakdown-1 §5）。

代码核验要点：

- server.py:761 组合根 `service = SnapshotService(config)` 构造点存在，可注入只读 client；server.py:733-752 的 `mode != "live"` 提前返回分支需调整，但 `backend/app/server.py` 在 backend-2 Allowed Files 内——注入路径合法。
- `HedgeOpenLiveClient.__init__`（hedge_open_live_client.py）只存 key/secret 等字段、不发任何请求——"创建 client 不发请求"成立；`_require_whitelisted` 在任何签名原语之前拒绝未登记路径（注释明载）。
- config.py:312 已有 `BINANCE_HEDGE_API_KEY`（组合根复用，无新环境变量）；config.py:114 `GROUP_B_REFRESH_SECONDS=1800` 可作为建议档位；snapshot_service.py 的 `_global_source_cache[source_id]` 独立 due + "只有成功才推进时间戳"（FR-2）纪律为展示"失败即未知"提供落点。
- 方案 §6.2/§6.3/§8/§9 #10 已同步 E-4（不投影 last-good、不适用在三态外、组合根注入）；接口约定 §3 真值表态 3/态 4、§7 禁令、§9 I-1..I-5 与 §E-4 逐字一致。

[TASK_RESULT v2]
任务 ID: interface-amendment-review-1
执行结果: completed（完成）
结果摘要: HIGH_RISK 接口修订复核（DeepSeek，只读）完成：§E-4 三项 Human 裁定已在方案 §6/§8/§9、implementation-interface-v0.9.md 与 backend-2 任务卡中一致同步。失败即未知不投影 last-good、不适用在三态外（asset=null 无 flag）、SnapshotService 组合根只读注入均闭环；真值表保持、缓存隔离、负费率 PAPI 边界与不进 negative_funding_status 无回退。组合根路径经代码核验可落地。评审结论 ACCEPT。
产物: [none（只读复核未写文件；核验结果均在本回执内）]
检查结果:
1. [pass] §E-4 与方案同步：§6.2 组合根注入段落、§6.3 不适用与失败即未知、§8 server.py 注入范围、§9 #10 验收全部落实 E-4 三项，无遗漏。
2. [pass] 接口约定一致：§3 真值表态 3（未知，checked_at=null）与态 4（不适用，asset=null、无 flag、checked_at 与全表同值）、刷新失败行为（last-good 仅内部重试不投影）、§9 I-1/I-2 依据已更新为 §E-4，无 pre-E-4 残留。
3. [pass] backend-2 任务卡一致：第 4 点展示侧要求与验收「三态与不适用」「失败覆盖输出」「组合根只读注入」「缓存隔离」逐字对应接口约定；「即使 APP_HEDGE_EXECUTOR != live 也构造并注入」明确。
4. [pass] 真值表保持：有现货腿行仅已满/未满/未知三态；不适用在三态外且不称未满；前端表外组合 fail-closed 为未知（规则 6）；四字段组合一致性由后端测试锁定。
5. [pass] 组合根路径可落地：server.py:761 构造点可注入；HedgeOpenLiveClient.__init__ 不发请求、构造安全；_require_whitelisted 在签名前拒绝未登记路径；复用 config.py:312 已有 key，无需新配置。
6. [pass] 安全边界未放宽：§3 预检每次新鲜读取（接口约定 §7 禁令 1-4）、缓存隔离有专门测试（方案 §9 #11）、负费率 PAPI 边界保留、collateral_cap 不进 negative_funding_status（接口约定 §2/§11）。
7. [pass] backend-2 Allowed Files/Stop 边界合规：含 server.py 允许组合根注入；禁 config.py、frontend/**、fixtures/**、阶段记录；无新环境变量/配置项/订单开关；全部 fake transport、禁真实请求与 Start gate 变更。
8. [pass] 数据源与 allowlist 未回退：restricted-asset 不签名只带 X-MBX-APIKEY、仅读 maxCollateralExceededAsset、openLongRestrictedAsset 不读不存（E-2/A-3）；展示与预检两路均受 exact allowlist 与 host 硬绑定管控。
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-03 01:02:15 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本原始回执交回 Bookkeeper（codex）；Bookkeeper 核验 ACCEPT 后解除 blockers 并投递 implementation-backend-2（claude_glm，status_revision 6，投递前以当时 status.json.revision 校对），由 Human 启动；后端提交 SHA 固定后（门 1）方可投递 implementation-frontend-1。ACCEPT 不授权实现、开闸或实盘。
[/TASK_RESULT]
