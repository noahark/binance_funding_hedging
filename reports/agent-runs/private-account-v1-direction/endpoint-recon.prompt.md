<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: kimi（首选，night-collection 先例）或 gemini（llms-full 研究先例）
adapter_cmd: 用户以「读文件并执行 PROMPT BODY」一行指令发至模型终端
started_at:
completed_at:
session_id:
outputs:                   # endpoint-recon-<model>.md（逐字落档）
next_dispatch: 摸排落档 → Fable5 消费其结论出 stage design 全套 packet（executor: user 中转）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是「私有账户数据接入 v1」stage design 前的**端点摸排研究员**。
这是纯文档研究任务：**禁止**任何网络请求、签名调用、写代码；不需要
也不得请求任何 API key。产出将作为 stage design 的输入，并在 H_intake
由 live discovery 逐条核验。

## 输入

1. `docs/private-account-v1-direction-draft.md`（FROZEN 方向基线，
   §3.1/§3.3/§3.6 为本任务的端点清单来源）
2. `llms-full.txt`（币安官方文档 dump，一切端点主张必须引行号）
3. `reports/api-samples/api-samples-index.md` 与
   `reports/api-samples/night-collection-2026-07-05/`（已有公开端点
   实抓样本，可直接引用其字段结构）
4. `backend/services/private_client.py`（现有白名单实现，了解
   (method, path, base_url) 三元组格式）

## 交付物：`reports/agent-runs/private-account-v1-direction/endpoint-recon-<你的模型名>.md`

### A. 端点档案（核心，覆盖基线 §3.6 表中全部端点）

对既有白名单 4 项 + 新增 E1/E1b/E2/E2b/E5/E3/E4/E6 + 公开估值候选，
逐端点一节：

- method / path / base_url（papi/sapi/api 族归属）
- 鉴权类型（NONE / USER_DATA 签名）
- 请求参数表（名称/类型/必填/默认）
- 响应字段表（字段名/类型/语义/是否敏感数值）——night-collection 已有
  实抓样本的直接引用样本结构
- **文档权重值**（找不到明确权重的如实标注"文档未见"，禁止猜测）
- 相关错误码（尤其权限类 -2015/-1002、限频类 -1003/429）
- 统一账户（非专业版）适用性的文档证据（引原文行号；证据不足处
  明确标注"需 H_intake 实测"）

### B. 限频预算表初稿（按基线 §3.6 三场景）

初始化一轮 / 稳态每 60s 一轮 / 借币探测每 1h 一轮（上限 50 调用）——
按文档权重合计各场景用量，与官方限额（fapi/api/sapi 各族分别）对比，
给出安全余量结论与最紧的瓶颈端点。

### C. 现货估值价格源建议

对比 `/api/v3/ticker/price`、`/api/v3/ticker/bookTicker` 等候选的
权重（全量 vs 单 symbol）、字段、更新语义，给出推荐 + 理由。

### D. websocket 订阅研究附录（纯研究，服务未来修正轮）

- listenKey 生命周期（创建/保活/失效，标注涉及的 HTTP 动词——这些
  动词当前在永久禁令内，仅记录事实）
- user data stream 事件类型与消息结构（余额/持仓/订单事件），统一
  账户与经典账户的流差异
- 明确声明：本附录仅为未来「只读账户 websocket 修正案」的研究输入，
  本轮任何代码不得实现。

## 纪律

- 每条主张附 llms-full.txt 行号或 night-collection 样本路径；无出处
  的推断明确标注「推断，需实测」；
- 不写文件到本文档以外的位置、不改工作树、零网络调用；
- 末尾注明模型身份与当前本地北京时间。你的输出将逐字落档。
