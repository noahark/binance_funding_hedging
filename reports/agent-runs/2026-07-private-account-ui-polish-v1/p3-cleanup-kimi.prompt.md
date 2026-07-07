<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: p3-cleanup (round-3, 合并前清理)
target_model: kimi          # implementer/fix-author（非 reviewer）
role: fix_author
role_chain: fix=Kimi → review-1=Codex(delta) → review-2=Claude/Fable5(delta 独立终审)
basis: 30-review-1-v1.1.md / 50-review-2-v1.1.md 两位 reviewer 明确点名的 2×P3(逐字给出修法)
prior_delivery_head: ec327466a9ec28be6158aedfc53541ea2b3e463c
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Kimi 终端
next_dispatch: 交回 → bookkeeper 核 diff 仅为 2×P3 + 测试绿 → Codex review-1(delta) → Fable5 review-2(delta) → pre-accept → merge --no-ff
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的 **fix_author（Kimi）**。round-2 已两轮
ACCEPT;用户决定**合并前清掉 2 个 P3**(reviewer 已逐字指定修法)。**只做这两处,别的一律不碰。**

## 只允许的两处改动(frontend/index.html)

1. **删孤儿 `.sidebar-footer` CSS**:item 8 已删除 DOM `.sidebar-footer` 块,遗留两处 CSS 规则:
   - `frontend/index.html:135` 附近的 `.sidebar-footer { … }` 样式块;
   - `frontend/index.html:498` 附近移动端媒体查询里的 `.sidebar-footer { display: none; }`。
   删除这两处孤儿规则(若同一选择器与其他规则合并,只移除 `.sidebar-footer` 相关部分,勿动其他选择器)。

2. **修静态占位文案**:`frontend/index.html:570` 附近
   `<p class="subtitle" id="private-panel-subtitle">只读资产视图</p>` 的静态文本
   `只读资产视图` 改为中性值 `资产更新时间 —`(与 renderPrivatePanel 的新文案标准一致;
   该占位在渲染前被 JS 覆盖,改为中性值即可)。

## 硬红线

- **不改任何其他文件、不改任何逻辑/JS 行为**;不动 `renderPrivatePanel` 逻辑、不动后端/schema/契约/测试断言语义。
- 不新增功能、不顺手重构。diff 必须**只含**上述 2 处(CSS 删除 + 1 处静态文本)。
- 若某处现存文本/行号与描述略有出入,按**意图**定位(孤儿 `.sidebar-footer` 选择器、静态 subtitle 占位),不要扩大范围。

## 验证(全绿方可交回)

```
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -c "import json,jsonschema;jsonschema.validate(json.load(open('frontend/fixture/public-market-snapshot.json')),json.load(open('schemas/api/public-market/snapshot.schema.json')))"
```

self-check 若有断言直接依赖静态占位原文(应无,因其被 JS 覆盖),据实调整对应断言;否则勿动 self-check。

## 交回物

- 仅 `frontend/index.html` 的 2 处改动(如 self-check 需微调则附带)。
- 在 `40-fix-report.md` 追加一节:两处 what/where、diff 范围声明(仅 2×P3)、测试输出。
- 提交后回报 `head_sha`;**不要**改 `status.json` 的 review/fingerprint 字段(bookkeeper 复算落定)。

（RECEIPT 由 bookkeeper 更新,你不改本 prompt 文件。）
