# Task Handoff: asset-transfer-live-t1-backend

## Source Report (author-only; immutable after task end)

- task_id: `asset-transfer-live-t1-backend` / role: Implementer / target model: opus5（provider `anthropic`）
- stage_id: `2026-08-06-asset-transfer-live-v1` / created_at: 2026-08-07 00:4x CST
- base_sha: `bb47d0213cd98942dc12b91b562926ff848bfdee` / delivery_sha: `pending`

### 交付内容

后端划转通路：新建 `asset_transfer` 幂等存储 + `POST /api/asset-transfer` 端点，
复用既有 `HedgeOpenLiveClient.universal_transfer`（本体零改动）。

**实际修改范围（4 个产品文件，全部在 Allowed Files 内）**

| 文件 | 改动 |
|---|---|
| `backend/asset_transfer/__init__.py` | 新建，仅包 docstring |
| `backend/asset_transfer/store.py` | 新建，`AssetTransferStore` + 四态常量 |
| `backend/app/server.py` | 新增路由 `POST /api/asset-transfer`、handler 三方法、模块级校验函数与常量、`_build_asset_transfer_client`、`run()` 接线、两个类属性 |
| `backend/tests/test_asset_transfer.py` | 新建，40 个测试 |

### 关键实现决定

1. **幂等键放在本地数据库**。币安 `/sapi/v1/asset/transfer` 没有 `clientOrderId`
   之类的幂等键——这是它与下单接口的关键差异，重复提交会真的转两次钱。
   `client_request_id` 作主键（唯一约束由 SQLite 保证），`store.begin()` 返回
   `is_new=False` 时 handler **直接回放首次记录，零外发**。并发重复请求同样只有
   一个能拿到 `True`。
2. **`unknown` 是显式终态，不是失败**。传输失败 / 5xx / HTTP 200 但响应缺 `tranId`
   → `unknown`。把这些显示成"失败"会诱导用户重试，而钱可能已经转了。one-shot：
   任何情况都不重试。
3. **未预期异常也必须落终态**。`_dispatch_asset_transfer` 用 `except Exception`
   兜底写 `unknown`，否则记录会永远停在 `pending`，前端拿不到结果——这在动钱路径
   上等价于把用户置于"不知道钱转没转"的状态。
4. **方向映射只在服务端**。请求体不接受币安 transfer type；`(from, to)` 两种合法
   组合映射到冻结枚举 `TRANSFER_TYPE_PM_MAIN` / `TRANSFER_TYPE_MAIN_PM`（从客户端
   模块 import，不复制字面量）。有测试证明请求体里塞 `type` 字段不生效。
5. **币种白名单跟随转出账户**。必须出现在该账户当前快照余额里。快照未就绪 → 503
   且零外发（无法校验就不放行）。
6. **划转客户端独立于 `APP_HEDGE_EXECUTOR`**。与既有 `_build_restricted_asset_client`
   同模式。理由：该开关语义是"对冲开单任务是否真实发单"，划转是用户手动发起的独立
   动作，不属于开单链路。**这是需要评审确认的判断**——见下方「不能假设的事实」。
7. **不做本地余额充足性预判**（快照 60 秒可能过期），余额不足由币安返回 `-4015`
   后原样回显。

### Human O-1/O-2 决定的落实

代码中**不存在** `transfer_gate` 与 `TRANSFER_MAX_USDT`（`grep -rn` 全仓零命中）。
动钱约束收敛为：`confirm: true` 必填 + 全量落库审计 + `client_request_id` 幂等。

### 命令与结果

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests
  -> 1508 passed in 111.24s
     （基线 1468 + 本任务新增 40；无删除、无跳过、无告警失败）
```

原始输出：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.pytest.txt`

**边界核验（命令实测，非叙述）**

- `git diff --stat HEAD -- backend/services/hedge_open_live_client.py` → 空（`universal_transfer` 本体零改动）
- `git diff --stat HEAD -- frontend/` → 空（零前端改动）
- `git diff HEAD -- backend/app/server.py | grep "^+.*path =="` → 仅 1 条 `/api/asset-transfer`
- `grep -rn "transfer_gate\|TRANSFER_MAX_USDT" backend/ frontend/` → 零命中
- `PRAGMA table_info(asset_transfer)` → `amount` 与 `tran_id` 均为 `TEXT`；主键 `client_request_id`
- store 内无 `SUM(` / `AVG(` / `TOTAL(`

### 契约文档位置（dispatch 验收检查 8）

`/api/asset-transfer` **未**写入 `docs/api/public-market-contract.md`：实测该文档
只记录 public-market 快照 payload 契约，既有的 `/api/hedge-open-tasks`、
`/api/borrow-tasks` 等操作端点同样不在其中（`grep -c "hedge-open-tasks"` → 0）。
本端点的契约记录位置沿用既有惯例：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/00-intake.md`
§4.2（请求体）、§4.4（幂等）、§4.6（错误分类）加本交接件。schema 体系同理不涉及
（`schemas/api/public-market/snapshot.schema.json` 只描述快照）。

### 未完成事项

- T2 前端未接线（本 dispatch 明确不含前端）：划转按钮当前仍是零请求预览。
- 划转成功后的快照刷新按 `00-intake.md` §4.5 由前端调用既有
  `POST /api/public-market/cache-refresh`，本任务未内嵌。
- 端点尚无任何真实调用验证（本任务全离线，未启动服务、未触实盘）。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.handoff.md`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.pytest.txt`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/00-intake.md`、
  `backend/asset_transfer/store.py`、`backend/app/server.py`、
  `backend/tests/test_asset_transfer.py`
- 执行：Bookkeeper（deepseek）核验本交接件与 delivery commit，把
  `current_task.state` 由 `reported` 推进到 `verified` 并封存
  `base_sha..delivery_sha`；随后按 Human 决定路由 T2 前端 dispatch 或实现后 review-1。
- 关卡：Bookkeeper 核验；此后 Human 决定是否先做 T2 再评审，以及合并授权。
- 不能假设的事实：
  1. **端点从未被真实调用过**。全部证据来自离线桩测试；没有任何一笔真实划转被发出。
  2. **划转不受 `APP_HEDGE_EXECUTOR` 控制**（实现决定 6）。即使服务以
     `disabled` 模式启动，只要有 hedge API key，该端点就会真实划转。这是本任务的
     判断，不是 Human 的明确指示，**请评审确认是否符合预期**。
  3. `unknown` 状态意味着结果真的未知，**不得**在任何下游把它折叠成失败或成功。
  4. 幂等键是 `client_request_id` 本身，不是请求内容哈希：同一 id 改金额重放会
     返回首次记录而非按新金额划转（有测试固定该行为）。
  5. 本阶段 Bookkeeper 兼任 review-1 且无 review-2（Human 越门，`status.json`
     的 `blockers` 已记录），**不得**因评审层薄而放松核验标准。
  6. 基线提交 `8e17027` 由本终端在 T1 开工前执行（Human 当面授权，dispatch 验收
     检查 9 要求脏基线时停止）；`status.json` 的 `base_sha` 仍是 `bb47d02`，
     因此 `base_sha..delivery_sha` 区间会包含该基线提交的 A/B 两组改动——它们
     不是本任务交付，按 `AGENTS.md` §8「发现的范围三分类」应记为范围外。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

任务 ID: asset-transfer-live-t1-backend
执行结果: completed（完成）
结果摘要: 后端划转通路交付：新建 asset_transfer 幂等存储与 POST /api/asset-transfer，复用既有 universal_transfer（本体零改动）。幂等键落本地唯一索引（币安该端点无幂等键，重放零外发）；超时/5xx 记 unknown 不重试；按 Human O-1/O-2 未实现闸门与单笔上限。全量 1508 passed（基线 1468+40）。端点尚未被真实调用过。
产物: [backend/asset_transfer/__init__.py, backend/asset_transfer/store.py, backend/app/server.py, backend/tests/test_asset_transfer.py, reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.handoff.md, reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.pytest.txt]
检查结果: [全量离线回归 1508 passed（基线 1468+新增 40）: pass, 幂等重放零外发（桩调用计数断言）: pass, 超时/5xx→unknown 且不重试: pass, 请求校验全覆盖（两方向映射/同账户/confirm/非法金额含 1e3/白名单/UUID/缺字段）: pass, 金额红线（amount 与 tran_id 列 TEXT、无 SQL 金额聚合、原样透传）: pass, Human O-1/O-2 落实（transfer_gate 与 TRANSFER_MAX_USDT 全仓零命中）: pass, 边界未越过（universal_transfer 本体与 frontend/ 零改动、仅新增 1 条路由、未合并/未部署/未触实盘）: pass, 端点契约记录位置已说明（不入 public-market-contract.md，沿用既有操作端点惯例）: pass]
阻塞项: [none]
本地北京时间: 2026-08-07 00:52:10 CST
下一步模型: deepseek（本阶段 Bookkeeper，status.json.bookkeeper）——由 Human 启动其终端
下一步任务: 读取：reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json、reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.handoff.md、reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.pytest.txt；执行：核验交付与 delivery commit，将 current_task.state 由 reported 推进到 verified 并封存 base_sha..delivery_sha；关卡：Bookkeeper 核验通过后，由 Human 决定先做 T2 前端还是直接进实现后 review-1，以及是否授权合并

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- 核验时间: `2026-08-07 00:34:38 CST`（Bookkeeper: deepseek，本阶段兼任 review-1）
- source_sha256: `7192e7d4a8d9fbedc1b1f688ad3e221fe7737a44136f0afb0de7aa9c77f6fee3`（marker 前 9696 字节）
- 核对的 status revision: `1`（核验时 `current_task.state=reported`）
- delivery_sha: `1f91241bcc2eab61eb0b3e5727f9e2bffd88ee88`（`git rev-parse` 解析 handoff 的 `pending`；`git rev-parse HEAD` 一致）
- 核验结论: **通过（状态推进 `reported` → `verified`，封存 `base_sha..delivery_sha` = `bb47d02..1f91241`）**
- 通过依据（可复现命令）:
  - `git show 1f91241 --name-status` → 7 个文件全部在 dispatch Allowed Files 内（server.py M、asset_transfer/ 两新建、test_asset_transfer.py 新建、handoff/pytest.txt/status.json 新建）
  - `git diff 8e17027 1f91241 --stat -- backend/services/hedge_open_live_client.py` → 空（`universal_transfer` 本体零改动）；`-- frontend/` → 空（零前端改动）
  - `git diff 8e17027 1f91241 -- backend/app/server.py | grep "^+.*/api/"` → 2 条命中：1 条路由 `if path == "/api/asset-transfer"` + 1 条 docstring 注释，实际新路由恰 1 条
  - `grep -rn "transfer_gate\|TRANSFER_MAX_USDT" backend/ frontend/` → 零命中（Human O-1/O-2 落实）
  - 独立重跑 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests` → **1508 passed in 111.76s**（与 handoff 声称一致，基线 1468 + 新增 40；原始输出见本目录 pytest.txt）
  - 实现审读：幂等唯一约束 + `begin()/resolve()` 锁外不持锁外发；`unknown` 显式终态（异常/5xx/200 无 tranId）不重试；请求校验（UUID/方向/同账户/金额正则挡 1e3 与负号/白名单/confirm）无绕过路径；金额列 TEXT 无 SQL 聚合
- review-1（deepseek 兼任，独立 review 工具交叉核验）: **verdict REWORK**，5 条发现全部 `in-range`（指向 1f91241 交付代码，无 pre-existing）：
  1. **[high]** 划转端点不受 `APP_HEDGE_EXECUTOR` 控制（`server.py:1244` 仅查 `offline`/API key），默认配置即可真实动钱、无启动警示，与系统「executor=disabled 默认安全态」心智模型冲突（`config.py:108`）；修复形态涉产品决策，待 Human 定（见 status.json `next`）
  2. **[medium]** 业务结果一律 HTTP 200，前端须只看 `body.status`；建议 `unknown` 响应加 `needs_review` 提示字段并写入 T2 验收契约
  3. **[medium]** `pending` 卡死：begin 后 resolve 前进程中断则记录永久停在 pending（安全不重复转账，但不可推进）；建议运维文档 + 启动巡检告警，禁止自动重发
  4. **[low]** handler 级同 id 并发测试缺口（现有幂等测试为串行）；建议补线程并发断言「只外发一次」
  5. **[low]** 429 与 4xx 同归 `failed`；429 处于「可能未受理」灰色带，建议显式归 `unknown`
- 后续状态: `status.json` revision 2 将 `current_task.state` 置 `verified`、写入 `delivery_sha`；review-1 REWORK 修复 dispatch 待 Human 决定修复形态后创建（`rework_count` 0→1）
- 追加（2026-08-07，Human 决定落档）: Human 决定——R1（high，划转端点不受 executor 控制）**接受现状不修**，暴露面已记 `PROJECT_STATE.md` Live Risks `[OPEN][ACCEPTED][2026-08-07]`；R2–R5 由 Human 与 opus5 讨论处置；本阶段不创建修复 dispatch，review-1 未关闭（非 ACCEPT 亦未开修复轮），`status.json` revision 3 记录，`rework_count` 保持 0

## Errata (append-only)
