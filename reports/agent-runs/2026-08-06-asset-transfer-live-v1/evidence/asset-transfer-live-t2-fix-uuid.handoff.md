# Task Handoff: asset-transfer-live-t2-fix-uuid

## Source Report (author-only; immutable after task end)

- task_id: `asset-transfer-live-t2-fix-uuid` / role: Implementer（bounded repair）/ target model: opus5（provider `anthropic`）
- stage_id: `2026-08-06-asset-transfer-live-v1` / created_at: 2026-08-07 CST
- base_sha: `036fcd143ff436a879fe884082784af7a373bcbd`（T2 前端）/ delivery_sha: `bbe81b0`

### 缺陷来源：实盘首笔划转失败

Human 在真实界面点击首笔划转（1 USDT，统一 → 现货），被后端 400 拦下：
`client_request_id 必须是 UUID 格式`。**钱未动**——请求在服务端校验阶段即被拒，
从未到达币安。

Human 提供了浏览器实际发出的请求体：

```json
{"client_request_id":"c886-84-03-46-bc0e13","from_account":"unified",
 "to_account":"spot","asset":"USDT","amount":"1","confirm":true}
```

`c886-84-03-46-bc0e13` 为 4-2-2-2-6 共 16 个十六进制字符；标准 UUID 是
8-4-4-4-12 共 32 个，且 v4 的第三段必须以 `4` 开头（此处为 `03`）。即
**用户浏览器的 `crypto.randomUUID()` 返回了非标准格式的值**。

**根因未查明**（WebView / 隐私插件 / 中间层改写皆有可能），且**不再追查**：
真正的缺陷是 T2 实现把一个环境 API 的**输出格式**当成了保证。修复方式让根因
不再影响正确性。

诊断过程（排除法，命令实测）：

- `curl` 以合法 UUID + `confirm:false` 探测后端 → 返回 `confirm_required`，
  证明后端 UUID 校验本身正常，且该探测不会外发（`confirm` 在解析阶段拦下）。
- `ps -o lstart` → 服务启动于 01:19:37，晚于 T2 提交 `036fcd1`（01:16:49），
  排除「服务跑旧代码」。
- `curl http://127.0.0.1:8787/ | grep` → 服务吐出的 `index.html` 含 T2 新代码，
  排除「静态文件未更新」。

### 修复

`newTransferRequestId()` 不再调用 `crypto.randomUUID()`。改为只向环境索取随机
**字节**（`crypto.getRandomValues`，缺失时 `Math.random` 兜底——幂等键只需唯一，
不需密码学强度），版本位（`0x40`）、variant 位（`0x80`）与 8-4-4-4-12 分段格式
全部由本函数拼装。任何环境下输出都是合法 UUID v4。

### 实际修改范围（2 个产品文件，后端零改动）

| 文件 | 改动 |
|---|---|
| `frontend/index.html` | `newTransferRequestId()` 重写；`__appHelpers` 导出该函数供自检 |
| `frontend/self-check.js` | 新增断言块 75y2（幂等键生成器回归防线） |

### 回归防线（self-check 75y2）

1. **把 `crypto.randomUUID` 替换成当天那个坏实现**（`() => 'c886-84-03-46-bc0e13'`），
   断言生成器输出不受影响——这条直接复现故障条件；
2. 连续 200 次生成，每个都严格匹配 v4 正则（版本位 `4`、variant 位 `[89ab]`），
   且 200 个值互不重复；
3. 删除 `crypto.getRandomValues` 走兜底路径，输出仍合法；
4. 用后端 `server.py` 的**同一条正则**反向验证生成结果被接受——这条把前后端
   契约钉在一起，任一侧改正则都会让自检变红。

### 命令与结果

```text
node frontend/self-check.js  -> 全部自检通过（含新增 75y2）
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests
                             -> 1518 passed in 116.48s（后端零改动，持平）
```

- 自检输出：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.selfcheck.txt`
- **实盘验收证据**：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.live-acceptance.txt`

### 实盘验收（Human，2026-08-07）

修复后 Human 硬刷新页面（**未重启服务**——静态文件由服务实时读取）重试，
**首批真实划转成功**，只读导出自 `data/asset-transfer.sqlite3`：

| 发起时间 | 方向 | 币种/数量 | 状态 | 交易所流水号 | 端到端耗时 |
|---|---|---|---|---|---|
| 01:38:31 | unified → spot | USDT 1 | `succeeded` | 398029611774 | 363 ms |
| 01:39:21 | unified → spot | USDT 50 | `succeeded` | 398029775970 | 667 ms |

两笔的 `client_request_id` 均为合法 UUID v4（`79d3fc9e-d7e2-4d2e-b9a0-a9b23f4ab21a`、
`18af8ba1-cb1e-4018-8346-b127b9969395`），审计表字段完整、`error_code`/`error_message`
均为 `NULL`。**至此 `POST /api/asset-transfer` 完成首次真实调用验证。**

### 这次故障暴露的测试边界（供评审与后续参考）

后端 50 个用例 + 前端自检在故障发生前全部为绿，却没能拦住它：它们跑在 Node 里，
`crypto.randomUUID` 是好的。**离线测试无法覆盖「环境 API 行为异常」这一类缺陷**，
只有真实点击能暴露。这与本阶段一直强调的「端点从未被真实调用过」是同一件事的
两面。新增的 75y2 通过**注入坏实现**把这类缺陷纳入了离线可测范围。

### 未完成事项 / 仍然开放

- R3（`begin()` 后 `resolve()` 前进程中断 → 永久 `pending`）按 Human 决定未修。
- R1 只有启动提示，没有开关；`disabled` 模式启动时该端点依然真实划转。
- 仅验证了 `unified → spot` 方向与 `succeeded` 路径；`spot → unified`、`failed`、
  `unknown` 三条路径**未经真实验证**（仅离线断言）。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.handoff.md`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.live-acceptance.txt`、
  `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.selfcheck.txt`、
  `frontend/index.html`、`frontend/self-check.js`
- 执行：Bookkeeper（deepseek）核验本修复轮，按 `AGENTS.md` §8 将 T2 交付物的
  `rework_count` 由 `0` 递增为 `1`（实盘验收发现的缺陷所触发的再交付），封存
  delivery `bbe81b0`，并将 Human 的实盘验收事实写入 `PROJECT_STATE.md`。
- 关卡：Bookkeeper 核验后，由 Human 决定是否授权合并 main。
- 不能假设的事实：
  1. 本任务同样**无 dispatch**（Human 直接指示，延续前两笔的越门安排）。
  2. 实盘只验证了 `unified → spot` 的成功路径；反向与三条异常路径仍只有离线证据。
  3. R3、R1 的缺口未变——**不得**因实盘成功而在记录里淡化它们。
  4. 前端为静态文件、服务实时读取：前端修复**不需要重启服务**，硬刷新即可。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

任务 ID: asset-transfer-live-t2-fix-uuid
执行结果: completed（完成）
结果摘要: 实盘首笔划转被后端 400 拦下（钱未动）：浏览器 crypto.randomUUID() 返回非标准值 c886-84-03-46-bc0e13（16 位，标准 32 位）。缺陷在于把环境 API 的输出格式当保证；改为只取随机字节、格式自行拼装。修复后 Human 实盘验收通过：1 USDT 与 50 USDT 两笔 unified→spot 均 succeeded，有交易所流水号。自检新增坏实现注入回归；后端零改动 1518 passed。
产物: [frontend/index.html, frontend/self-check.js, reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.handoff.md, reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.selfcheck.txt, reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.live-acceptance.txt]
检查结果: [实盘验收通过：两笔真实划转 succeeded 且有交易所流水号（审计表只读导出）: pass, 幂等键生成器注入坏实现后仍产出严格 v4（复现故障条件）: pass, 200 次生成无重复且无 getRandomValues 时兜底仍合法: pass, 生成结果被后端同一条正则接受（前后端契约钉死）: pass, node frontend/self-check.js 全部通过: pass, 后端 1518 passed（后端零改动）: pass, 根因诊断为排除法命令实测（后端校验正常/服务非旧代码/静态文件已更新）: pass, R1 与 R3 缺口未因实盘成功而淡化: pass]
阻塞项: [none]
本地北京时间: 2026-08-07 01:43:20 CST
下一步模型: deepseek（本阶段 Bookkeeper，status.json.bookkeeper）——由 Human 启动其终端
下一步任务: 读取：reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.handoff.md、reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t2-fix-uuid.live-acceptance.txt、reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json；执行：核验本修复轮与实盘验收证据，将 T2 交付物 rework_count 由 0 递增为 1，封存 delivery bbe81b0，把 Human 实盘验收事实写入 PROJECT_STATE.md；关卡：Bookkeeper 核验后由 Human 决定是否授权合并 main

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
