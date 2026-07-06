<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: running            # pending | running | done | blocked | escalated
target_model: claude_glm (glm-5.2) FRESH 专职 bookkeeper 会话（禁止兼任实现）
adapter_cmd: 用户在 source ~/.binance-keys 后的终端启动 fresh claude-glm 会话，发「读文件执行 PROMPT BODY」一行指令
started_at: 2026-07-05T16:29Z (UTC) / 2026-07-06 00:29 CST
completed_at: (进行中 — H_intake G1-G5 全过，已进第三步并行派工)
session_id: bookkeeper fresh claude-glm (this session)
outputs:
  - scripts/discovery-capture-private-v1.py（G5 自查通过：12 签名白名单==status.json + 公开 ticker/price、零 POST/PUT/DELETE、key 零片段、py_compile OK；E2 已修 isIsolated=false）
  - reports/api-samples/2026-07-private-account-v1/20260705T232800Z/（PASS run：14/14 调用 HTTP 200，E3/E4/E6 全 200；evidence-index.md 含 sha256 全表 + 实测 X-MBX/X-SAPI weight 头 + chain_tier=1 next_hourly）
  - reports/.../10-design.md §2.A 附录（§2.A.1 权重 / §2.A.2 三场景预算 / §2.A.3 字段矩阵 / §2.A.4 脱敏标记表 / §2.A.5 链命中 + §5 fixture 引用）
  - backend/tests/fixtures/private-account-v1-design.json（设计期合成 fixture：6 行覆盖 §3.4/§3.5 向量 + private_account 三态；Task A 产出真值后替换）
  - status.json: planned -> blocked (auth -2015) -> implementing（blockers/escalation 已清，attempts 含 blocked+passed 两轮）
H_intake: G1 分支 OK / G2 E3-E4-E6 全 PASS / G3 权重冻结 / G4 字段矩阵+fixture / G5 禁令自查全过。committed_sha+base_sha 待 H_intake 提交后二次回填（status.json 不含自身 sha）。
next_dispatch: 第三步并行派工（executor: user 中转两个实现终端）：
  Task A -> fresh claude-glm 后端会话（backend/**、schemas/**、docs/api/**）；task-a-glm-backend.prompt.md
  Task B -> Kimi 前端终端（frontend/index.html、frontend/self-check.js）；task-b-kimi-frontend.prompt.md
  实现终端红线：不 commit / 不碰 status.json / 完成后机械执行任务书末尾 R10 收尾段。
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-v1` 的 **bookkeeper（stage operator，
单一写者）**。你不写任何业务代码；本 stage 是并行模式试运行 #2 +
stage 分支制首跑。你与 Task A 实现者同为 claude_glm 模型但**必须是
不同会话**（已在 status.json 披露）。

## 第一步：读取（顺序执行）

1. `docs/parallel-development-mode.md`（R1-R10）+ `AGENTS.md` Hard Gates
2. 本 stage 目录：`00-intake.md`、`00-task.md`、`10-design.md`、
   `status.json`
3. `docs/private-account-v1-direction-draft.md`（FROZEN 基线）
4. `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi.md`

## 第二步：H_intake（硬门 G1-G5，全过才派工）

1. **G1**：`git branch --show-current` 必须 ==
   `stage/2026-07-private-account-v1`；否则停，报告用户。
2. 确认 `BINANCE_API_KEY`/`BINANCE_API_SECRET` 存在（只验存在性，
   禁止打印任何片段）；缺失 → 停，提醒用户 `source ~/.binance-keys`
   后重启本会话。
3. **G2**：编写一次性脚本 `scripts/discovery-capture-private-v1.py`：
   - 端点 = status.json endpoint_whitelist 12 项 + 公开
     `/api/v3/ticker/price`（全量一次）；白名单脚本内硬编码；
   - 账户级响应**抓取即脱敏**（数值换占位、保留字段名/类型；URL 剥
     query string）；脱敏逻辑在脚本内可复核；
   - **每次调用记录 `X-MBX-USED-WEIGHT-*` / `X-SAPI-USED-*-WEIGHT-*`
     响应头**（G3 输入）；
   - maxBorrowable 只抓 2 个样本资产；E1/E1b 各抓一次用于归属比对；
   - 落档 `reports/api-samples/2026-07-private-account-v1/<UTC-ts>/`
     + `evidence-index.md`（sha256 全表）。
   - **E3/E4/E6 任一失败 → status=blocked，原始错误码落档，升级用户，
     禁止静默降级**；E2/E2b/E5 失败 → 记录四级链命中档位，不阻塞。
4. **G3**：据实测修订摸排预算表 → 写入 10-design **§2.A 附录**
   （冻结预算表：三场景 × 实测权重 vs 限额；重点 papi maxBorrowable
   与 E3/E4 实测权重；既有 fundingRate top-N 计入稳态场景）。
5. **G4**：同一附录内冻结 E2/E2b/E5/E3/E4/E6 字段矩阵（raw path →
   契约字段 → 类型 → 脱敏标记），并按 10-design §5 生成设计期
   fixture（脱敏值）。
6. **G5**：自查脚本无 POST/PUT/DELETE、无 key 片段落档。
7. 提交 H_intake（本 packet + 脚本 + 证据 + 附录 + fixture +
   status.json: planned→implementing, base_sha=该提交, h_intake.committed_sha
   同步）。运行 `python3 scripts/validate-stage.py 2026-07-private-account-v1
   --phase checkpoint` 确认 PASS（含分支门）。

## 第三步：并行派工

1. 回填两份任务书 RECEIPT（status=running + started_at），向用户输出
   两条一行派工指令（Task A → 另一个 fresh claude-glm 实现会话；
   Task B → Kimi 终端），提醒实现终端**不 commit、不碰 status.json、
   完成后必须机械执行任务书末尾 R10 收尾段**。
2. 预审 raw output 落档后：你按 R4 做落盘前对账（重算该任务工作树
   diff vs 最后一轮 diff.patch，差异须由 fix-note 完全解释），然后
   串行提交 H_A（backend）→ H_B（frontend），重算指纹，
   status=review_1，validate checkpoint + pre-review。

## 第四步：正式评审与终态

1. review-1：`review-prompts-templates.md` T1/T2 填指纹后另存 dispatch
   文件派 A→fresh Kimi、B→fresh GLM（role=**first_reviewer**）。
2. review-2：T3 填好交用户中转 Codex（read-only）。
3. 全 ACCEPT → status=**stage_accepted_waiting_user**，validate
   pre-accept，向用户报告。**红线：你 can_accept_final=false，禁止把
   status 翻到 accepted——那是用户门（上一 stage 的时序疑点已写进
   规则）**。合回 main 的动作同样只在用户明确验收后执行（能 ff 则
   ff，否则 main 侧 merge commit，回填 stage_branch 七字段）。

## 红线速查

- 签名调用仅白名单 12 项 + 公开端点；websocket/listenKey 铺垫代码 =
  永禁；key 零片段；中途加端点 = R3 升级；
- 单一写者：git 与 status.json 只有你动；
- 每个 dispatch 的 RECEIPT 由你回填；next_dispatch 标 executor:self
  的必须执行或按三类原因 escalated。

完成或阻塞时：回填本文件 RECEIPT，向用户简报（本地北京时间 + 下一步
+ 可直接粘贴的移交指令）。
