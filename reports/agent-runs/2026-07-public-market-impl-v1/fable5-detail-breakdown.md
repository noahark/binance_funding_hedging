# Fable5 开发细节拆解:公开市场后端实现 + 前端对接

- 阶段 ID(建议):`2026-07-public-market-impl-v1`
- 拆解人:Claude Fable 5(anthropic,经 Claude Code 接入)
- 角色:development detail breakdown(按 stage-delivery.yaml,本拆解计为
  design involvement,review-2 若由 anthropic 担任须走披露式 override)
- 依据(权威顺序):用户批准的方向综合稿 → `docs/product/PRD.md` →
  `docs/api/public-market-contract.md`(已冻结,head `a25e431` 验收)→
  `schemas/api/public-market/snapshot.schema.json` → 本文件
- 前置状态:契约阶段 `2026-07-public-market-contract-v2` 双审 ACCEPT,
  规范化样本与 schema 已冻结;margin 端点已证实需要 API key,Phase 1 不用。

## 1. 阶段目标

把已冻结的 `public-market-snapshot/v1` 契约变成可运行系统:

1. Claude-GLM 实现后端快照服务:抓取公开端点 → 规范化 → 分类 →
   通过 `GET /api/public-market/snapshot` 提供 schema 合法的 JSON。
2. Kimi 实现前端市场表工作台页面,仅消费上述契约。
3. 集成验证:前端从真实本地后端加载数据,证据可复跑。

一个验收边界:三个任务全部 review-1 通过 + 集成证据 + 一次 review-2。

## 2. 非目标(本阶段禁止)

- 任何签名接口、API key、私有账户端点、user data stream。
- 任何下单、借币、还款、划转、平仓代码路径。
- 开平仓规划计算器 UI(quantity 对齐、名义额校验等 PRD §6.4 逻辑)——
  这是纯函数领域逻辑,需要单独一轮契约冻结后再做;本阶段前端只做
  市场表展示。若用户希望提前,需明确批准并补契约。
- 手动开仓票据、规划器雏形、下单按钮、补腿提示、持仓管理入口均不
  在本阶段实现。前端不得为了占位提前做这些交互。
- websocket、深度行情、自动刷新轮询(简单的手动刷新按钮除外)。
- 数据库。文件缓存 + 内存即可。
- 部署、进程守护、公网暴露。服务只绑定 127.0.0.1。

## 3. 所有权与文件边界

| 路径 | Owner | 规则 |
|---|---|---|
| `backend/**` | Claude-GLM | Kimi 禁止写入 |
| `frontend/**` | Kimi | Claude-GLM 仅可添加静态托管路由指向该目录,不得改其内容 |
| `schemas/api/public-market/**` | 冻结 | 双方只读;要改 = 契约变更,任务置 blocked 上报,禁止静默修改 |
| `docs/api/public-market-contract.md` | 冻结 | 同上 |
| `reports/api-samples/public-market-contract-v2/**` | 冻结证据 | 只读 |
| `prototypes/fake-ui/index.html` | 冻结参考 | 只读;中文工作台视觉风格的基准 |
| `reports/agent-runs/2026-07-public-market-impl-v1/**` | Controller | 任务报告按 owner 分文件 |
| `docs/`、`agents/`、`workflows/`、`scripts/` | 本阶段不动 | 发现 harness 问题走 escalation,不顺手修 |

跨界即 REWORK,无论代码质量如何。

## 4. 任务拆分(status.json 中为一等公民 task 记录)

每个任务独立记录 `base_sha`/`head_sha`/`diff_fingerprint`(任务级)、
implementer、reviewer、verdict、测试证据路径。

### Task A:后端快照服务(Claude-GLM,senior_developer)

交付物:

- `backend/` Python 包,依赖最小化:标准库 + `jsonschema`;HTTP 框架
  允许 FastAPI+uvicorn 或标准库 `http.server` 二选一,在
  `20-implementation-backend.md` 里记录选择理由;测试用 `pytest==8.3.*`
  (锁版本,上次 grok 用 9.x 自测的教训)。
- 数据流:fetch(`/fapi/v1/exchangeInfo`、`/fapi/v1/premiumIndex`、
  `/fapi/v1/fundingRate`、`/api/v3/exchangeInfo`)→ normalize →
  classify → assemble snapshot → 出口前用冻结 schema 自校验,不合法
  则返回 503 并落 warning,禁止返回不合法快照。
- 行为规范(全部来自已冻结契约/PRD,评审对照点):
  - 仅收录 futures `status == "TRADING"`;`contractType` 为
    `PERPETUAL` 或 `TRADIFI_PERPETUAL`。
  - `TRADIFI_PERPETUAL` → `asset_tag=BSTOCK`;asset_tag 与 route_class
    独立判定。
  - route_class:现货腿存在且 `isMarginTradingAllowed=true` →
    `MARGIN_SPOT_CANDIDATE`;仅现货 → `SPOT_ONLY_CANDIDATE`;无现货 →
    `PERP_ONLY_EXCLUDED`。`margin_public.source` 保持 `"unverified"`。
  - negative_funding_status 优先级:PERP_ONLY → BSTOCK → SPOT_ONLY →
    PRIVATE_BORROW_VALIDATION_REQUIRED,顺序不可交换。
  - 所有小数字段:内部 Decimal、序列化为字符串,禁止 float。
  - `funding_history` 仅取按 `|lastFundingRate|` 排序的 top-N
    (默认 N=20,配置项),其余为空数组——控制 `/fapi/v1/fundingRate`
    调用量;实现须记录实际请求数与限频余量观察。默认值 20 已获
    本轮设计确认,除非用户显式变更,不得在实现中改为其他默认值。
  - `summary` 各计数必须等于 `rows` 聚合,不允许独立计算两遍后不校验。
  - 快照带磁盘缓存(TTL 默认 60s,配置项);`--offline` 模式从
    fixture 目录读原始样本,测试与 CI 一律 offline,禁止联网。
  - 契约阶段的三条 warnings(margin 未验证、lastFundingRate 语义、
    BSTOCK 无现货腿)必须原样保留在服务输出中。
- 测试:normalize/classify 纯函数单测(用冻结 raw 样本做 fixture,含
  非 TRADING、TRADIFI_PERPETUAL、无现货腿等边界)、schema 正反向
  校验(复用契约阶段 10 个篡改样本的思路)、offline 端到端一次。

### Task B:前端市场表(Kimi,minimal_change_engineer)

交付物:

- `frontend/` 免构建静态页(纯 HTML/CSS/JS,无打包工具链),视觉风格
  对齐 `prototypes/fake-ui` 的中文工作台基准。
- 数据源只有两个:`fetch('/api/public-market/snapshot')`(相对路径,
  经后端静态托管,无 CORS)与本地 fixture 模式(字节级复制冻结的
  `normalized/public-market-snapshot.json`,不得手改)。正式本地页面
  必须通过后端同源托管访问真实 `/api/public-market/snapshot`;fixture
  仅允许用于离线测试或无后端时的自检证据,不得作为默认运行数据。
- 展示要求:
  - 市场表:symbol、asset_tag、route_class、`last_funding_rate`、
    `next_funding_time`(转北京时间显示)、mark/index price、
    negative_funding_status、ui_flags。
  - `last_funding_rate` 的列名/悬浮文案必须写"最近更新的资金费率",
    禁止写"已结算"或"预测"——语义未证实,这是契约 warning 的传导。
  - `warnings[]` 必须在页面可见区域展示,不得吞掉。
  - BSTOCK 行明显标识;PERP_ONLY_EXCLUDED 默认可过滤。
- 交互范围:仅允许市场表展示、筛选/搜索、手动刷新、warning 展示、
  BSTOCK/route_class/negative_funding_status 标识。不得实现开仓票据、
  规划计算器、下单流程、账户状态、持仓状态或任何交易意图按钮。
- 硬边界:不直连 Binance;不自行发明分类/换算逻辑(展示层格式化除外);
  契约缺字段 → 任务置 blocked 提契约更新请求,禁止绕过。
- 测试:fixture 模式渲染自检清单写入 `20-implementation-frontend.md`,
  含"6 行样本全渲染、warnings 可见、BSTOCK 标识、时间转换正确"。

### Task C:集成验证(Controller 执行脚本化命令,不写产品代码)

- 启动后端(live 或 offline 均可,记录用的哪种)→
  `curl http://127.0.0.1:<port>/api/public-market/snapshot` 存原始响应 →
  `jsonschema` 校验 0 errors → 浏览器/无头加载前端页面确认从该端点
  渲染成功。全部命令与输出进 `60-test-output.txt`,可复跑。
- 集成产生的快照响应作为证据存入阶段目录(带时间戳)。

## 5. 评审路由与披露

- review-1(任务级,交叉,fresh read-only session):
  - Task A(GLM 实现)→ Kimi 审,`30-review-1-backend.md`。
  - Task B(Kimi 实现)→ 新会话只读 Claude-GLM 审,
    `30-review-1-frontend.md`;禁止复用 controller 会话。
- review-2(阶段级):designer/breakdown = Fable5(anthropic)。
  首选 codex/GPT(本阶段无设计参与);anthropic Claude 兜底时必须走
  披露式 override:`reviewer_prior_involvement=breakdown`,且按新规
  把本拆解文件本身列为受审对象、以方向综合稿和 PRD 为更高权威。
- 两个 implementer provider(zhipu_glm、kimi)在本阶段均写过代码,
  按 `final_reviewer_not_code_author` 无条件不得担任 review-2。
- Grok 维持排除,不参与实现与评审。

## 6. 风险点与评审聚焦

1. Decimal 纪律:任何 `float()` 出现在价格/费率/数量路径即 P1。
2. negative_funding_status 优先级顺序写反——用显式序列实现并单测。
3. 非 TRADING 符号混入(grok 事故复发点),必须有专门测试。
4. `summary` 与 `rows` 不一致——聚合校验测试。
5. 前端偷偷解释语义(lastFundingRate 标注、自造路由徽标)——review-1
   聚焦检查文案与契约 warning 的一致性。
6. 限频:`/fapi/v1/fundingRate` 逐 symbol 调用失控;top-N + 缓存兜住,
   实现报告须记录请求计数。
7. 缓存陈旧:`data_time`/`generated_at` 必须真实反映抓取时间,前端
   显示数据时间,不得显示为"实时"。
8. 测试联网:offline 之外的任何测试联网即 REWORK。
9. `__pycache__`/`.pyc` 进 diff——.gitignore 先行,派发前 controller
   校验工作区干净。

## 7. 证据与门禁(逐条对照 stage-delivery.yaml)

- 每任务完成即本地 evidence commit;review 前
  `scripts/validate-stage.py 2026-07-public-market-impl-v1 --phase
  pre-review` 必须 PASSED。
- 指纹公式不变:`head_sha + ":" + sha256(git diff --binary
  <base>..<head> -- . ":(exclude).../status.json")`;任务级与阶段级
  分别记录;禁止任何替代指纹协议。
- 评审用 status.json 记录的 base..head 固定区间,不用移动 HEAD。
- 本地 commit 不代表允许 push/merge;阶段终态
  `stage_accepted_waiting_user`,等用户开启下一方向。

## 8. 检查点文件

- `00-intake.md`、`00-task.md`(controller/designer 从本文件收敛)
- `20-implementation-backend.md`(GLM)/`20-implementation-frontend.md`(Kimi)
- `30-review-1-backend.md`、`30-review-1-frontend.md`
- `40-fix-report-<task>.md`(如有 REWORK)
- `50-review-2.md`、`60-test-output.txt`、`70-handoff.md`、`status.json`
  (含 tasks 一等公民记录)

## 9. 留给用户的三个决定

1. 规划计算器 UI 本阶段确认排除。原因:quantity 对齐、名义额校验、
   开单轮次和滑点兜底都需要单独契约冻结;本阶段只做公共行情市场表。
2. funding_history top-N 默认 20。该值作为本阶段实现默认配置,后续可
   在产品设置中开放,但本阶段不得擅自改默认值。
3. 前端本阶段确认不做复杂交易交互。只做市场表、筛选/搜索、手动刷新、
   warnings 展示和状态标识;正式本地页面必须请求同源后端 API,fixture
   仅用于测试。

---

本地北京时间: 2026-07-03 20:10:55 CST
下一步模型: 用户批准后 → Claude-GLM(controller)建阶段目录并派发 Task A/B
下一步任务: 用户审阅本拆解,确认第 9 节两个决定,然后启动
`2026-07-public-market-impl-v1` 阶段
