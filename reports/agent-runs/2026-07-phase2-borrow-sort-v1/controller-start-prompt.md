<!-- ============ RECEIPT（审计元数据，执行者填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: claude_glm (controller/bookkeeper session)
adapter_cmd: 用户粘贴 PROMPT BODY 至 claude-glm controller 终端
started_at:
completed_at:
session_id:
outputs:                   # H_intake commit sha / discovery 证据目录 / 派工时间
next_dispatch: task-a-glm-backend.prompt.md + task-b-kimi-frontend.prompt.md（并行）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **controller 兼 bookkeeper**
（用户指定的单一本地执行会话）。本阶段按
`docs/parallel-development-mode.md`（ADOPTED-TRIAL）首次试运行并行模式。
你的 dual-hat（兼 Task A 实现模型）已在 status.json 披露。

## 第一步：读取（顺序执行，不得跳过）

1. `docs/parallel-development-mode.md`（全篇，重点 R1-R9）
2. `reports/agent-runs/2026-07-phase2-borrow-sort-v1/00-intake.md`、
   `00-task.md`、`10-design.md`、`status.json`
3. `docs/phase2-direction-draft.md`（FROZEN 基线，冲突时以它为准）

## 第二步：H_intake（本阶段 base 锚点）

1. 确认环境变量 `BINANCE_API_KEY`/`BINANCE_API_SECRET` 已注入（只确认
   存在性，**禁止打印/记录任何片段**）。缺失 → 停，报告用户。
2. 编写一次性 discovery 脚本 `scripts/discovery-capture-phase2.py`：
   - 端点 = status.json `endpoint_whitelist` 四项 + 公开
     `GET /fapi/v1/fundingInfo`；
   - HMAC-SHA256 签名 GET，仅此五个调用，脚本内白名单硬编码；
   - `maxBorrowable` 只抓 2 个资产样本（`BTC`、以及日费率靠前的一个
     候选资产）；
   - **抓取即脱敏**：落档前整体剥离 URL query string；账户级响应删除
     账户标识字段并将额度类数值替换为占位（保留字段名与类型信息）；
     脱敏逻辑在脚本内、可复核；
   - 落档 `reports/api-samples/2026-07-phase2-borrow-sort-v1/<UTC-ts>/`
     + `evidence-index.md`（sha256 全表 + 抓取时刻 + 端点清单）。
3. **E5 gate**：`/papi/v1/margin/maxBorrowable` 失败（4xx/权限/账户形态
   不符）→ status=blocked，写明原始错误码，升级用户，**禁止**静默改用
   /sapi。其余端点失败同样如实记录后升级。
4. 据实抓在 `10-design.md` §2 追加附录：每端点实际字段名、raw JSON
   path、类型、单位（属 intake 范畴的补写，标注你的署名与时间）。
5. 提交 H_intake（本 packet 全部文件 + discovery 证据 + 脚本 +
   status.json: status=designing→implementing, base_sha=该提交）。
   运行 `scripts/validate-stage.py <stage> --phase checkpoint` 确认。

## 第三步：并行派工

1. 在两个 dispatch 文件的 RECEIPT 块填 status=running + started_at，
   然后把各自 PROMPT BODY 原样交付：Task A 在你的实现上下文执行（或按
   用户安排的 GLM 实现会话）；Task B 由用户粘贴给 Kimi 终端。
2. 提醒两端：**实现终端不 commit、不碰 status.json**；改动只留工作树。
3. 嵌入预审触发（每任务实现自评完成后）：生成该任务的
   `embedded-review-<a|b>-round1.diff.patch`（reviewer 所见工作树 diff，
   git diff 输出原样落档），用户把对应 pre-review prompt + patch 路径
   交给 fresh 只读评审会话；raw output 落
   `embedded-review-<a|b>-round1.raw-output.md`；有 blocker 则实现方修复
   后最多再一轮（封顶 2 轮，不计 rework_count）。你是唯一落盘写者。

## 第四步：串行落盘与正式评审

1. 双任务预审通过后：跑全部测试（pytest + node self-check），原始输出
   落 `60-test-output.txt`；按 commit_order H_A（backend）→ H_B
   （frontend）提交；重算指纹；status=review_1；
   validate-stage checkpoint + pre-review 两道门。
2. 正式 review-1（committed 指纹）：用 `review-prompts-templates.md`
   模板填指纹/路径后派 A→fresh Kimi、B→fresh GLM 只读会话。
3. review-2：模板填好后由用户交 Codex（read-only）。
4. 全 ACCEPT → status=stage_accepted_waiting_user，validate-stage
   pre-accept，向用户报告（你 can_accept_final=false）。

## 红线速查

- 签名请求仅白名单四项 + 公开 fundingInfo；任何 POST/PUT/DELETE、
  交易语义端点 = 永久禁止。
- key 任何片段不得出现在日志/报告/落档/对话。
- 耦合面（funding_interval_hours / daily_funding_rate / rows 有序性）
  变更请求 → 停手，R3 升级，禁止本地 fix。
- 并行红线突破 → 记录 breach，回退串行完成本阶段。

完成或阻塞时：回填本文件与各 dispatch 的 RECEIPT 块（经你落盘），
向用户输出简报（本地北京时间 + 下一步）。
