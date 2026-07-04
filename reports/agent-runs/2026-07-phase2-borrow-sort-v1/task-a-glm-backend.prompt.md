<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: claude_glm (Task A implementer)
adapter_cmd: controller 在 H_intake 完成后交付 PROMPT BODY
started_at:
completed_at:
session_id:
outputs:                   # 20-implementation-backend.md / 自测结果摘要
next_dispatch: pre-review-task-a-by-kimi.prompt.md（嵌入预审 round 1）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **Task A 实现者**（后端）。
权威规格 = `reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md`
§1/§2/§3（先通读全文 + `00-task.md` + status.json hard_constraints）。
本文只列执行纪律与边界，规格细节以 10-design 为准，冲突时 10-design 赢。

## 交付物

1. `backend/services/private_client.py`（新）：单一 HMAC 出口 +
   deny-by-default `(method, exact-path)` 白名单（status.json
   endpoint_whitelist 四项）+ GET-only + 出站审计日志 + 1h TTL 缓存 +
   429/-1003 退避 + env 缺失优雅降级。
2. fundingInfo 接入（公开客户端路径）+ `funding_interval_hours` /
   `daily_funding_rate`（decimal.Decimal，禁 float）+ rows 后端排序
   （abs 日费率降序、null 末尾、symbol 升序 tie-break）。
3. `borrow_validation` 块装配（三态语义；classic_margin 全候选行 /
   portfolio_account 仅 bounded top-N，见 10-design §3.4；VIP0 取档）。
4. schema v0.2 + `docs/api/public-market-contract.md` amendment（引用
   H_intake discovery 样本路径为证据）。
5. 测试：10-design §3.3 全部 daily-rate 向量 + §3.2 六项安全门负向
   单测 + 排序全序 + 三态 schema + 降级分支 + live/offline 双模式
   jsonschema PASS；既有 54 测试零回归。
6. `20-implementation-backend.md`：改动清单、测试原始输出、自查表。

## 硬边界（违反即预审 blocker）

- 允许/禁止文件按 10-design §3.1；`classify.py`/`normalize.py`/
  `frontend/**` 零触碰。
- 枚举与优先级零改动；route_class/negative_funding_status 取值不受
  borrow_validation 影响。
- key/secret 任何片段不得进代码、日志、报告、测试 fixture。
- 耦合面三项（interval 字段/日费率字段/有序性）按 10-design §1 实现，
  发现需要变更 → 停手上报 controller（R3），禁止自行调整。
- **不 commit、不碰 status.json**；改动只留工作树，报告写完即停，
  由 bookkeeper 负责提交与指纹。

完成后输出：改动文件清单 + 测试摘要 + 「等待嵌入预审 round 1」。
