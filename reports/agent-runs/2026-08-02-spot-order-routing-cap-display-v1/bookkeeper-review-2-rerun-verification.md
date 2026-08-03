# review-2-reality-rerun ACCEPT — Bookkeeper 核验与交接

核验时间：2026-08-03 10:55 CST

Opus5 的回执格式完整，明确给出 `评审结论: ACCEPT`。Bookkeeper 再次直接核验固定两端：
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5` 与
`e99974ad934af5117b0c2385e5545f9861812d5d` 均可解析，当前 HEAD 为 delivery SHA，且
`git diff --check 1a55781..e99974a` 通过。

## 最终技术结论

本 stage 的 HIGH_RISK 技术评审已全部通过：

- 正费率现货买入在 bStock 或抵押额度名单命中时走普通 Spot；负费率现货卖出保留 PAPI，不读名单。
- 普通 Spot 下单、查单和审计使用 leg 行 endpoint；不会带 `sideEffectType`，也不会把普通 Spot 的
  51169 误归到统一账户路径。
- 行情页在**标的列**展示「抵押额度已满」或「抵押额度未知」，不看费率方向；未知不会被说成未满，且
  展示缓存与下单预检隔离。
- 精确 12 条 endpoint 的 allowlist 守卫和签名前 fail-closed 保护恢复有效；全量后端测试为 1215 passed，
  前端 self-check 通过。用户已另行完成页面高亮与 bStock 下单联调确认；这不是评审替代品，但与代码/测试
  结论一致。

`rework_count` 为 2，两个正式返工均已闭环；技术 blockers 已清空。`review-2 ACCEPT` 仅关闭技术评审
闸门，不等于合并、部署、开闸或实盘授权。

## 非阻塞遗留（不要求本轮返工）

1. **归档后的文档死链**：v0.9 契约的权威顺序指向 stage 内接口约定；stage 归档后该路径会失效。阶段
   收尾时应把耐久的权威说明指向 canonical 文档。
2. **一处说明的归因不够精确**：docstring 所述「展示 client 只调名单 GET」实际由 SnapshotService 的调用面
   保证；allowlist 负责拒绝未登记 endpoint。行为安全，文字可在阶段收尾澄清。
3. **已接受的运营前提**：行情快照会按现有刷新节奏携带 hedge API key 读取名单，并注入完整但
   deny-by-default 的 client；没有运行时权限探测、自动普通 Spot 补腿或本轮平仓设计。现有
   `PROJECT_STATE.md` 的实盘风险并未因此改变。

下一步由 Human 决定是否授权合并；即使授权合并，部署与实盘操作仍须分别、明确授权。
