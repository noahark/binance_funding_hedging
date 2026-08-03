# Bookkeeper boundary audit — task-breakdown-1

日期：2026-08-03

## 已核验通过的部分

- 四份规划产物均存在，且无代码、契约、schema、状态或旧 dispatch 越界修改；原始回执已封存于
  `evidence/task-breakdown-1.opus5.raw.md`。
- 后端/前端 Allowed Files 零交集；前端等待后端本地提交及 Bookkeeper 固定 SHA 的顺序正确。
- 现货 base asset 单点、方向无关的展示高亮、预检/展示缓存隔离、五条 exact allowlist 和 review
  provider 隔离均与已 ACCEPT 方案一致。

## 需 Human 裁定，故本回执暂不验收

### D-1 展示刷新失败后的真值

已 ACCEPT 方案 §6.3 规定「读取失败（网络、限频、鉴权失败）→ 未知」；接口约定 I-1 改为
「若曾成功，则刷新失败仍显示 last-good 已满/未满，仅从未成功时未知」。它可能是合理的缓存显示
取舍，但会改变操作者在本次刷新失败时看到的状态，不能由 Planner 代为决定。

### D-2 「不适用」是否成为第四个展示状态

方案 §6.3 规定三态；接口约定 I-2 新增「没有可解析现货腿 → 不适用、无徽标」。这也合理，
但它让三态规则扩展为四种有效组合，须由 Human 明确接受或改为未知。

### D-3 展示读取 client 的实现路径相互矛盾

`backend/app/server.py:733-752` 仅在 `APP_HEDGE_EXECUTOR=live` 时构造
`HedgeOpenLiveClient`；`backend/services/snapshot_service.py:151-165` 目前只在 private channel
开启时以 `BINANCE_API_KEY` 构造 `PrivateClient`。但 backend-2 同时要求展示读取经
`HedgeOpenLiveClient`，又禁止在 `APP_HEDGE_EXECUTOR != live` 时构造该 client，并且禁止修改
`backend/app/server.py`/`backend/config.py`。

因此当 hedge executor 非 live 时，SnapshotService 没有一个合法 client 可以读取名单；当前
packet 的“只要 private channel 开启就可读”的陈述无法实现。必须由 Human 选择展示读取是否只在
hedge executor live 时可用，或允许一次受控的 client 注入/构造路径；选定后应由 Planner 修正
接口约定和 backend dispatch，才可启动实现。

## Human 裁定后的处理（2026-08-03）

Human 选择：任意刷新失败即未知；无现货腿为不适用；SnapshotService 使用已有 hedge API key 的
受限只读 client，独立于 hedge executor 与 private channel。决策已写入
`docs/planning/2026-08-02-decisions-routing-and-cap-display.md` §E-4，并已同步到方案、接口约定、
后端任务卡和拆分记录。由于这改变了计划评审后的接口细节与组合根注入路径，进入实现前须进行一次
窄范围、跨 provider 的只读复核。
