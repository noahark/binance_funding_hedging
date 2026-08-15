只读评审任务：交付评审（有代码 diff）。不要修改仓库任何文件，不要实现，不要合并。

对象：分支 refactor/resolve-send-qty，提交 654dc95
base：main @ ce53f68（代码与 7d3dbed 零差异，仅多一个 docs 提交）
diff：5 files changed, 25 insertions(+), 3 deletions(-)
  backend/hedge_open_tasks/domain.py      +11（新增 resolve_send_qty）
  backend/hedge_open_tasks/service.py     ±1（第 3570 行调用点）
  backend/services/live_hedge_executor.py ±1（第 828 行调用点）
  backend/tests/fakes.py                  ±1（第 152 行调用点）
  backend/tests/test_hedge_domain.py      +11（新增 1 个函数级测试）

任务包（含硬约束）：docs/planning/duplicate-concept-consolidation-2026-08-15.task-change-1.md
方案依据：docs/planning/duplicate-concept-consolidation-2026-08-15.opus5.md §3
你的上一轮评审：同目录 *.review-grok-result.md（你已判定改动一零行为变化、可实现）

背景：这是乘数换算轮（leg-unit-size-conversion-2026-08-15.opus5.md r3）的前置铺垫。
方案里的「改动二」被你与另一 provider 双判 REWORK，**已剔除，不在本次交付内**。
本次只做改动一：发单数量取值三处收敛为一个函数，纯重构、零行为变化。

派发方（Opus 5）已独立复核，结论供你核对或推翻：
- 分支全量：2 failed / 1938 passed
- main 全量：2 failed / 1937 passed（差 1 = 本次新增测试）
- 两处失败同名同因，均与本改动无关：
  test_urlopen_only_in_designated_http_clients（触发文件 backend/services/public_ip_service.py，
    smooth-open-orders-v1-development-checklist.md:612 已记为已知基线失败）
  test_no_websocket_listenkey_scaffolding（触发文件 backend/app/server.py:105，
    该行是一条写着「there is no browser WebSocket」的注释，被字符串扫描误判；
    此条**未**被既有文档记录，属基线漂移，非本次引入）
- diff 未修改任何既有断言或夹具

请按仓库 AGENTS.md 的评审口径给出 ACCEPT 或 REWORK，逐条列出问题并附路径与行号。
以下五问必须逐一正面回答：

【问题 1】是否真的零行为变化？
三处调用点替换后，在 q_common 有值 / 为 None 两种输入下，行为是否与改前逐一等价？
特别核对 service.py:3570 那处：改前是 D.Decimal(task["single_amount"])，改后走统一函数。
类型、精度、异常形态是否有任何差异？

【问题 2】是否越界？
任务包 §4 列了七条明确不做（q_common is None 的拒发判断、倍数相关、
service.py:3612 的 q_common_str、DisabledHedgeExecutor、test_hedge_service.py:780、
改动二、死代码清理）。请逐条核对 diff 是否触碰。另请确认没有「顺手改进」相邻代码。

【问题 3】新增测试是否恰当？
test_resolve_send_qty_branches_and_type_equivalence 是否覆盖了该函数的全部分支？
是否存在多余的业务语义断言（任务包要求只测该函数本身）？断言 `is q`（同一性）
是否是正确的等价性表达？

【问题 4】函数落点是否合适？
放在 backend/hedge_open_tasks/domain.py。三处调用方均已 import domain as D。
是否引入了不当的依赖方向？domain 层承载这个职责是否合理？

【问题 5】是否引入了新问题？
包括但不限于：类型注解与实际契约是否一致（签名声明返回 Decimal，但 q_common 分支
直接返回入参，若入参非 Decimal 会怎样）；是否存在该函数被未来误用的路径；
派发方复核的两处基线失败判断是否成立。

约束：只读；不要改任何文件；不要合并；不要 push；结论写在你的回复里，
并同时写入 docs/planning/duplicate-concept-consolidation-2026-08-15.review-change-1-grok.md
（只写这一个文件）。
