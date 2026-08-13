# Identity

- task_id: `smooth-open-v1-review-1-kimi`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `20`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

对平滑开单 V1 的固定交付区间执行正式 Review-1。实现作者为 `gpt-5.6-sol`、provider `openai`；本审查由 provider `moonshot` 的 fresh Kimi 会话执行，满足跨 provider 与非自审要求。

只审查 Git 固定区间 `e955bdd300d214c5c3ad5c1acd629c0d21080165..24074b144dcdb745c511d866a75528a8930e8475`，禁止用移动的 `HEAD` 替代。该区间含一个 Bookkeeper 控制提交 `80eeef0171a121d91c96debdda81309df3fb9500` 和一个实现提交；dispatch/status 属控制上下文，不是产品交付。重点检查实现正确性、资金与并发契约、测试有效性、集成接缝和立即开单零回归，不重做产品设计。

# Allowed Files

Reviewer 完全只读，唯一允许写入的是以下确定路径的新 handoff：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-1-kimi.handoff.md`（create-only）
- Bookkeeper 预检命令 `test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-1-kimi.handoff.md` 已通过。

不得修改源码、测试、现有 handoff、设计文档、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md` 或其他文件；不得 commit、amend、push、merge、安装依赖、联网、读取凭证、控制服务、调用行情/账户/订单接口、下单或部署。允许运行 dispatch 指定的离线测试；测试产生的既有忽略缓存不构成文件修改权限，结束时 tracked worktree 必须保持干净且除唯一 handoff 外不得有新文件。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/12-smooth-open-v1-review-1-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Reviewer、Review-1 与 Task Handoff Evidence Contract 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`（含 Bookkeeper 核验与 R1 contested 裁定）
9. `docs/planning/smooth-open-orders-v1.md`
10. `docs/planning/smooth-open-orders-v1-development-checklist.md`
11. `docs/planning/ccxt-bookticker-recon-2026-08-13.md`
12. 用 Git 直接读取固定区间的提交、diff、产品源码和测试原件；不得以实现者摘要替代 raw diff。

启动先核对 stage/task/model/provider/status revision、`base_sha`、`delivery_sha` 全部一致，并以 `git cat-file -e <sha>^{commit}` 验证两个 SHA。任何不一致、handoff 路径已存在或无法保持只读，立即返回非接受结果。

# Acceptance Checks

1. **范围与交付完整性**
   - 以 `git diff --name-status base..delivery` 和 `git show delivery` 核对实际产品改动；控制文件只作上下文。确认实现文件属于原 dispatch Allowed Files，禁止的 executor、live client、preflight、scheduler、snapshot 与既有禁止测试零 diff。
   - 核对 `requirements.txt` 只固定 `ccxt==4.5.64` 且生产模块惰性 import；没有凭证、私钥、账户数据或绕过安全闸门的实现。

2. **公共盘口 provider**
   - 审查单 asyncio 线程、多 key watcher、引用计数、generation、失效/重连、同步线程边界、回调和 close/join；重点寻找 release/close 竞态、task 泄漏、旧 generation 复用、单侧阻塞拖死另一侧、锁内阻塞或回调死锁。
   - raw `info.b/B/a/A` 到 Decimal、合法性、spot/perp 时间戳和 `contractSize == 1` fail-closed 必须符合设计；normalized float、未知 multiplier 或保留断线快照不得进入 gate。

3. **Gate、持久化与并发原子性**
   - signed 阈值最多两位、方向 spread 严格 `>`、两腿各 `>=80%` 覆盖、5 分钟窗口和 market/manual/timeout 单一原因必须精确。
   - 审查 schema 迁移与 `open_smooth_gate`、`force_smooth_gate`、`prepare_attempt` 的事务条件；同一 seq 在市场通过与人工放行竞态下最多创建一次 attempt，`成交1次` 不能成为 gate 外额外成交。
   - 核对四条 running→非 running 写路径及非空 sentinel 测试；系统 pause/fatal stop 清 gate、Human resume 为同一未调度 seq 重开完整窗口，条件 UPDATE miss 不误清，结算路径不复活 gate。

4. **Worker/API 与立即链复用**
   - `Condition + wake_version` 必须阻塞等待且无忙循环；六类唤醒源、Start gate 关闭、pause/delete、stop、deadline 的锁顺序和生命周期不得丢唤醒或死锁。
   - smooth 只控制进入时机；两腿并发提交、同步等待、单腿、查单、结算仍走既有路径。任何绕开 `prepare_attempt`、直接 dispatch、重复计数、timeout 少于完整窗口或 provider 缺失时 fail-open 均是阻塞问题。
   - API 输入、400/409、任务读模型、动态盘口日志和 fill-once 可选 body 不得破坏 immediate/close 既有契约；smooth fill-all 必须禁用。

5. **前端与测试真实性**
   - 检查阈值输入位置/默认值/负数与零、任务卡既有信息和错误展示、盘口失效显示、正反向开单率、覆盖率、等待原因、日志展开与 fill-once 当前 seq 绑定；不得新增 timer 或恢复已知横向布局回归。
   - 评估新增测试是否真实覆盖 provider 生命周期、原子 gate、pause/resume、并发最多一次、API 与 UI，而非只断言实现细节或空值。
   - 可复跑离线命令：新增矩阵、核心 502 项、executor 75 项、前端 self-check 与字段绑定。全后端已知结果是 `1862 passed, 1 failed`；唯一失败若仍是 `test_private_client.py::test_urlopen_only_in_designated_http_clients` 报早于 base 的 `public_ip_service.py`，按已核验 packet 勘误视为 `pre-existing-independent`，不据此 REWORK。若出现第二个失败或失败对象改变，则按当前交付证据处理。

6. **正式 verdict**
   - 每条发现必须给精确文件/行、可复现证据、实际影响、最小修复要求，并按 `in-range | pre-existing-independent | pre-existing-release-critical` 三分类。`pre-existing-*` 必须给早于 base 的 Git 引入证据；范围外发现不改变 ACCEPT，但须按规则记录。
   - Reviewer 新提出的假设场景若要阻塞，必须满足 `AGENTS.md` §1 Scenario Admission；纯偏好、未来扩展或无证据标签不得 REWORK。
   - 有任何当前范围内资金、重复下单、竞态、数据语义、API 破坏或缺失必要证据的问题，返回 `REWORK`；否则返回明确、格式完整的 `ACCEPT`。Review-1 ACCEPT 只通过代码审查关，不授权安装、合并、服务控制或实盘。

# Stop

完成只读审查后，在唯一 handoff 路径按 Task Handoff Evidence Contract 写完整 Source Report；`base_sha` 与 `delivery_sha` 必须写固定直接 SHA，不得写 `pending`。Human Brief/控制台回执必须包含合规 `[TASK_RESULT v2]`、`评审结论: ACCEPT（接受） | REWORK（返工）`、问题记录、修复要求、中文交接三行，并以 `[/TASK_RESULT]` 作为最终非空输出。

下一步模型写 `Bookkeeper（codex）`；下一步任务必须是：读取本 Review-1 handoff；执行核验 source SHA-256、固定区间、发现分类与 verdict 并推进状态；关卡为 ACCEPT 后准备独立 Review-2，REWORK 则按发现准备原 Implementer 修复任务。不得自行修改状态、启动修复者或 Review-2。
