<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: stage-design (addendum, round-2 / v1.1-ui-polish-2)
target_model: codex         # designer；本 stage 既有 designer=Codex,增量设计仍归 Codex
role: designer              # 只产出设计,不写实现代码/不改源码正文
role_chain: designer=Codex → implementer=Kimi → review-1=Codex(设计者复核实现保真) → review-2=Claude/Fable5(独立终审)
governance: 用户裁决折入未合并 stage;round-1 两轮 ACCEPT 已 supersede(见 status.review_history);合并后新 diff 重走两轮 review。Fable5 不参与设计以保 review-2 独立。
delivery_base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4
current_stage_head_at_dispatch: c488c19c8aa299b0e0e345f6d030804439db8f36
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Codex 终端
next_dispatch: 设计交回 → Fable5 簿记审阅(design_review)→ 派 Kimi 实现 → Codex review-1 → Fable5 review-2
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的 **designer（Codex/GPT-5）**。本轮为
**增量设计 v1.1-ui-polish-2**:用户在 round-1(value_usdt + 前 4 项)已通过 pre-accept
后,追加 6 项个人账户面板打磨并裁决**折入本未合并 stage**。你已设计过 round-1
(`10-design.md`/`11-adr.md`);本轮只需为这 6 项增量补设计,复用既有基础。

**红线:只产出设计文档,不写实现代码、不改源码/schema/契约正文。** 实现由 Kimi 承担,
终审由独立 Fable5(你因 designer 身份 ineligible 终审)。

## 需求(WHAT 见 `00-task.md` §Scope 增补 item 5–10;此处给约束与决策点)

用户已拍板 3 项:① 折入当前 stage;② item「按折算价值排序」走**后端排序**;③ 审计文案口径 =
**如实承认已接入私有账户(配置 API key 时读取)、仍只读不下单/不划转**。

1. **余额行内折算(item 5)**:统一/现货余额每行金额后追加 `【: xxx.xx USDT】`(2 位小数)。
   来源 `balances_*[].value_usdt`(round-1 已加,勿改语义)。定清:2 位小数的取整方式
   (四舍五入 ROUND_HALF_UP?)、null/`"0.00000000"` 的展示占位、隐私开关须同时遮蔽金额与折算值。
2. **后端排序(item 6)**:在 `assemble_private_account` 内对 `balances_unified`、
   `balances_spot` 按 `value_usdt` **降序**、`value_usdt=null` 一律排最后、并给出**确定性
   tie-break**(建议 asset ASC,与既有 rows 约定一致)。
   **硬红线:仅排 private_account 余额数组;契约 frozen 的市场 `rows` 顺序
   (`docs/api/public-market-contract.md`「Row order (frozen)」,abs 费率 DESC)绝不可动。**
   排序是数组顺序 behavior 变更,**非契约字段/枚举变更**;确认 schema/契约无需改字段,
   并说明是否需在契约文档补一句「balances_* 按估值降序」的展示约定(additive 说明,不改既有语义)。
3. **删估值来源卡(item 7)**:前端移除「估值来源」overview 卡;payload 保留 `price_source`。
4. **删矛盾运行约束(item 8)**:删除侧栏「公开行情 · 只读展示 · 不连接 Binance」。
5. **时点合一(item 9)**:后端 `valuation.priced_at` 与顶层 `checked_at` **本为同值**
   (`snapshot.py`:`"priced_at": checked_at`);合并前端展示为单一时间;面板副标题
   「只读资产视图」→「资产更新时间 <时间>」,删除「估值时点」「检查时点」两张 overview 卡。
   定清:是否仅前端合并(推荐,后端字段保持不变以维持契约稳定)。
6. **审计文案校准(item 10)**:逐句核对以下前端文案与 backend 真实行为,按上述口径改写。
   backend 事实:私有通道 `_private.fetch_*` 走 **signed HMAC 真连 Binance**,deny-by-default
   (无 key/失败 → `classic_ref=None` → `private_account.verified=false`,公开快照仍渲染)。
   待核对处至少含:
   - 侧栏/顶栏「公开数据 · 只读」「公开数据」badge(顶栏 `subtitle`/`badge-row`);
   - `frontend/index.html` `WARNING_CHINESE[0]`「…需 API key（当前无 key 阶段）…」;
   - 「数据说明」panel 副标题「来自后端快照服务的公开验证限制与展示约定」。
   给出每条**精确中文替换文案**(memory `ui-chinese-first`),保「只读/不下单/不划转」为真、
   删「不连接 Binance/无 key 阶段/公开数据」等与私有通道矛盾的表述。区分「行情公开」与
   「账户需 key 私有只读」两类,不要把二者混为「公开数据」。

## 须读工件

`00-task.md`(§Scope 增补)、`10-design.md`、`11-adr.md`、`docs/api/public-market-contract.md`
(「Row order (frozen)」「Private Account … Amendment」)、`schemas/api/public-market/snapshot.schema.json`、
`backend/domain/snapshot.py`(`assemble_private_account`/`_usdt_value_optional`/`_quantize_rate`)、
`backend/services/snapshot_service.py`(私有通道 deny-by-default 事实)、
`frontend/index.html`(私有面板渲染 1155–1249 段、侧栏 534–537、顶栏 541–551、
`WARNING_CHINESE` 918–922、数据说明 553–567)。

## 产出

1. 在 `10-design.md` 末尾追加一节 `## v1.1-ui-polish-2 Design Addendum`:
   逐项(item 5–10)给出 HOW、涉及文件/函数、边界与降级、以及与冻结契约的关系确认
   (尤其「市场 rows 顺序不变」「无契约字段变更」两条要显式声明)。附 item 6 排序伪码与
   item 10 每条文案的**精确替换表**(原文 → 新文)。
2. 在 `11-adr.md` 追加 ADR(接编号)至少覆盖两条决策:
   (a) balances_* 后端排序(降序/null 末位/tie-break)与「不动 frozen rows」边界;
   (b) 审计文案口径(承认私有只读接入 vs 保留公开只读基调)。
3. 明确本增量的**契约变更门结论**:是否触发契约字段/枚举变更(预期「否」——
   value_usdt/priced_at 已存在,排序为数组顺序);若你判断需要契约文档补展示约定说明,
   指明是 additive-only 且 `schema_version` 不变。

不产出实现代码。设计交回后由 Fable5 做 design_review 并派 Kimi 实现。

（RECEIPT 由 bookkeeper 更新,你不改本 prompt 文件。）
