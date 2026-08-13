# Identity

- task_id: `smooth-open-v1-final-review-2-opus5`
- target_role: `Reviewer`
- target_model: `claude-opus-5`
- provider: `anthropic`
- status_revision: `53`
- required_skill: `agents/skills/reality-checker.md`

# Goal

在新建或执行 `/clear` 后的 fresh Opus 5 会话中，对平滑开单 V1 当前最终产品执行正式
Review-2，固定累计审查区间为：

```text
e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b
```

从 Human 冻结需求、实际页面与实盘观察、最终代码效果、独立证据、资金/运行风险和发布准备度出发，
给出明确 `ACCEPT（接受）` 或 `REWORK（返工）`。不得把 Implementer handoff 或累计 Review-1 的
`ACCEPT` 当成 Review-2 结论，须独立检查最终 delivery tree 与必要测试。

实现/修复作者 provider 为 `openai`、`xai`、`moonshot`；本 Reviewer provider 为 `anthropic`，与
全部实现/修复作者隔离。Opus 5/provider `anthropic` 曾参与本阶段计划修订；Human 现已明确指定 Opus 5
执行最终 Review-2。按 `agents/roles.md` 披露该设计背景：不得把自己曾参与的计划文本当实现证据，
必须以 Human 决策、固定代码、测试和运行事实独立裁定。

fresh Claude-GLM/provider `zhipu_glm` 已对完整累计区间完成 Review-1 并由 Bookkeeper 核验为
`verified-accept`。Human 已接受并冻结设计 §16.1 的 L1/L2/L3，以及“两位开单率显示等于阈值时没有
单独醒目标记”的限制；除非固定区间或已记录实盘证据满足各自重开条件，否则不得以偏好重新判
`REWORK`。

当前手动前台服务已加载 delivery `ad8c631`，`.venv` 已安装 `ccxt==4.5.64`，executor 为 live 且
Start gate=true；Human 已做过真实页面/订单验证。本任务仍完全只读，不授权访问或控制服务、读取凭证、
改 gate、创建或操作任务、下单、依赖变更、commit、push、merge、部署或任何新增实盘验证。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md`（唯一允许写入；create-only）

除此之外全部只读。不得修改源码、测试、计划、契约、既有 evidence/dispatch、`status.json`、
`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据，不得 commit，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md
exit 0（路径不存在，可由本 Reviewer 创建）
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/33-smooth-open-v1-final-review-2-opus5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 smooth 的 Human 决策、当前 live 运行、SHELLUSDT 验收、已接受限制、发布禁区及相关 live risk
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `53`、本 task_id 与累计固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer/Review-2 段
7. `agents/skills/reality-checker.md`
8. `docs/planning/smooth-open-orders-v1.md` 的最终 D1–D19、§6、§8–§9、§13、§16–§17
9. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的最终 §12、§15、§17；旧任务拓扑只作历史
10. `docs/api/public-market-contract.md` 的 smooth task、task-id logs、fill-once、fill-all 与 audit 契约
11. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md`，读取 Source Report 与 Bookkeeper Verification，但不得用其结论替代独立 Review-2
12. 五份实现/修复 handoff，按时间读取其交付声明与 Bookkeeper Verification，但不得把作者自证当真实效果：
    - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`
    - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md`
    - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-fix-gpt56sol-xhigh.handoff.md`
    - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md`
    - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-fix-kimi.handoff.md`
13. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`，只以其 F1 原始证据核查该缺陷在最终 tree 是否关闭
14. 固定区间原始 diff、最终 backend/frontend/requirements/API 契约和测试；按真实调用链追到组合根、provider、store、service、executor、server 与页面，不得用 moving HEAD 或 live 页面替代固定代码审查

不得扫描其他 stage、私有配置、凭证或运行时数据库；不得联网或触碰 `127.0.0.1:8787`。

# Acceptance Checks

1. **Human 需求到最终实际效果**
   - 独立证明 spot/perp 两个异步一档公共盘口订阅真实接入生产组合根；signed threshold 默认 `0.05`、支持零/负数/合法超长整数并按冻结两位百分点严格 `>`；两腿各自一档金额/数量覆盖固化 `q_common` 至少 80%。
   - 每轮 gate 5 分钟、超时复用立即链；`成交1次` 只 force 当前 gate 且不直接下单；达到目标次数后无第 N+1 单；两腿并发提交并同步等待，查单、结算和单腿暂停复用原链。
   - D17 smooth open 创建为 paused，Human 点 Start 才设杠杆、订阅、开 gate 和评估；未 Start 的 fill-once 不能绕过。immediate/close 行为不被误改。

2. **滑点通过到真实下单的速度与审计诚实性**
   - D15 smooth 放行后不再做 fresh 联网 preflight；D16 首轮杠杆在订阅/gate/首次评估之前完成且 dispatch 不重复；放行到两腿 client call 之前仅保留原子 `prepare_attempt`，无新增联网、sleep、审计 SQL或同步阻塞。
   - D19 market/manual/timeout 使用产生该结论的同一次盘口快照，放行后不二次 `latest()`；monotonic 分段覆盖 prepare、executor、两腿 client call 与 join，审计在下单返回后 best-effort 落库且失败不改变业务。
   - 对照已记录 SHELLUSDT 真实证据：显示 `+0.05%` 时量化值等于阈值故严格未过；随后 `0.15%` market pass，两腿 accepted，gate→两腿 client call 约 `4.523ms/4.893ms`。只能按证据范围使用，不得把一笔实盘推成所有行情保证。

3. **并发、生命周期和故障效果**
   - 从 ready、event loop、watcher、refcount、callback、service lock、release/close 全链判断：冷启动无僵尸订阅，subscribe/release 不与 `_smooth_lock` 互锁，持续异常不热循环，单侧失败不伪造另一侧，offline 零构造/零订阅。
   - 订阅失败必须暂停、清 gate、零 attempt/dispatch且可由 Human 再 Start；CCXT 缺失时 smooth create 明确 400、其他模式不受影响。当前依赖已安装不等于失败边界可省略。
   - pause/resume、进程重启、manual/market 竞态、deadline、gate 清理、次数与状态转换不能形成重复 attempt、多单或无审计旁路。

4. **页面操作体验与真实接线**
   - paused smooth 卡保留立即卡基础字段、阈值、按钮、错误和日志，但不展示伪盘口；running smooth 卡展示两侧连接、双向一档价量、开单率、覆盖率、轮次、倒计时和等待原因。
   - 共享 2 秒 tick 先刷新任务列表，再刷新“所有 running ∪ 仍存在且 expanded”的去重 task-id 集合；不按 mode/task_type/方向过滤、不新增 timer。页面刷新后 running smooth 不再因日志收起而长期误报数据不完整。
   - Human 接受“显示值等于阈值但严格未通过时没有单独醒目标记”的限制；只检查 wait reason/pass 状态是否诚实，不要求本轮改 UI、比较或精度。

5. **资金、订单和 Human 已接受限制**
   - create 首次 preflight、固化身份/route/数量、regular-spot forward 预划转、缺腿和 1000x open 拒绝仍成立；immediate 的每轮 fresh preflight 与既有杠杆语义未被 smooth 改动。
   - L1（Start OFF/stop 与 reserve→dispatch 竞态）、L2（上一轮结算耗时可能缩短下一 gate）、L3（未提交 threshold 在行情表重绘时可能复位）以及两位等值展示，是 Human 具名接受限制。说明实际影响、临时操作边界和重开条件；未满足重开条件不得仅凭偏好 REWORK。
   - 区分本交付与 `PROJECT_STATE.md` 中其他既存 live risk，不得把无因果的 reverse close 等范围外问题算作本交付 in-range；若为 pre-existing-release-critical，必须按规则提供早于 base 的 Git 证据并交 Human 决定。

6. **证据真实性与独立复跑**
   - 不只看测试名；抽查关键 fake/clock/executor/DOM 用例是否会在错误实现时变红，尤其 provider 冷启动/互锁/offline/热循环、gate 竞态和次数、D15/D16 顺序、D17 paused-create、D19 二次读取/前置 SQL/两腿串行、running 刷新并集。
   - 至少独立复跑专项、核心、executor/前端绑定及 `node frontend/self-check.js`；按风险决定是否复跑全后端。
   - 全后端已知唯一 `public_ip_service.py:47` 白名单失败只有在 Git 证明早于 base 且固定区间零 diff 时，才能分类 `pre-existing-independent`；失败对象或数量变化即不能沿用旧裁定。
   - 核对最终 API 契约和 delivery tree 一致，Human 实盘观察只能证明记录中的具体链路，不能代替并发/失败分支的可执行证据。

7. **发布准备度和回退边界**
   - 分别裁定：代码是否可进入 Human 最终合并决定；当前从 worktree 运行的 live 页面是否应继续用于 Human 验收；是否可以 merge/push/deploy；后续真实任务应采取什么最小数量和观察方式。不得执行这些动作。
   - 明确当前代码虽已在手动 live 进程加载、CCXT 已安装并出现真实成交，但分支尚未获批 merge/push/deploy；Review-2 ACCEPT 也不授权任何资金、服务或发布动作。
   - 给出具体可观察项和 fail-closed/暂停/人工收口边界，不提出脱离现有架构的新恢复系统。

8. **活文档与发现纪律**
   - 核对 `docs/` 活文档和 `PROJECT_STATE.md` 是否因最终交付需在阶段收尾同步，点名具体陈旧事实；纯收尾文档缺失不替代代码 verdict，只有会造成当前操作安全误导时才阻塞。
   - 每条发现按 `in-range | pre-existing-independent | pre-existing-release-critical` 分类，附当前证据、实际影响与最小修复要求；新假设须满足 `AGENTS.md` §1 Scenario Admission。
   - 任一 in-range 资金/订单、并发、生命周期、真实接线、契约或关键证据缺口 → `REWORK`；无 in-range 阻塞 → `ACCEPT`，同时用大白话列出 Human 在合并与后续实盘前必须知道的剩余限制。

9. **交接完整性**
   - 创建唯一 handoff，包含 immutable Source Report、Required Reading、Human Brief 与 marker；Reviewer `base_sha`/`delivery_sha` 使用累计固定 SHA，不得写 pending。
   - Human Brief 返回合规 `[TASK_RESULT v2]` 与 `评审结论: ACCEPT（接受） | REWORK（返工）`、`问题记录`、`修复要求`。`ACCEPT` 只进入 Human 最终决定，不授权发布或实盘。

# Stop

完成固定累计区间 Review-2、必要独立检查、唯一 handoff 和明确 verdict 后停止。不得自行修代码、改状态、
安装/卸载依赖、联网、读取凭证、控制服务、改 Start gate、创建或操作任务、下单、commit、push、merge、
部署或实盘。

`ACCEPT` 返回 Bookkeeper 核验后，由 Bookkeeper 用大白话向 Human 汇报最终效果、剩余风险以及合并/运行
选择；`REWORK` 返回 Bookkeeper 按发现范围处理。不得由本 Reviewer自行启动修复或把 Review-2
`ACCEPT` 当作 Human 合并、发布、服务或资金授权。
