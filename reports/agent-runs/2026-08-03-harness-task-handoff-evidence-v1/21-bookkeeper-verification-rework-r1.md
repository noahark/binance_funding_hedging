# Bookkeeper 核验：交接件契约实现拒收（R1）

核验时间：2026-08-03 16:46:56 CST
核验范围：`ed802bc64d5d1476a19b19aa58d773229b24bfa4..e7c0acb81831060369889143072787efe753e3f7`
实现回执：`evidence/20-claude-glm-implementation.raw.md`

## 结论

不封存本次交付。`current_task.state` 不标记 `verified`；原实现者须做一次最小修复，
`rework_count` 递增为 1。

## 已核验通过

- 交付 SHA 存在且当前 `HEAD` 与其一致；状态仅由 `dispatched` 变为 `reported`。
- 改动文件在 dispatch 允许范围内；无产品、资金、实盘、凭据或部署改动。
- `git diff --check`、两个状态 JSON 语法校验通过。
- `AGENTS.md` 保持现有 `TASK_RESULT v2` 字段和闭合标记，并以既有 `产物` 和
  `下一步任务` 引入新 stage 交接约定。
- `agents/roles.md` 已建立交接件的单一详细 authority，并正常路径改写了 Human 转交
  原始回执的规则。

## 拒收发现

### BK-001（in-range）：新任务不必读取详细交接契约，规则不可可靠执行

事实：项目启动规则要求模型读取匹配角色段；交接契约位于 `agents/roles.md` 的独立顶层
段。交付没有要求 Bookkeeper 在每个受该契约约束的新 task dispatch 的 `Inputs` 中列出
该详细契约，也没有在 Implementer／Reviewer／Bookkeeper 各自的必读项中作 scoped pointer。
下一模型可完全遵守现有启动顺序却只看到 `AGENTS.md` 的简短提醒，无法获得交接件结构、
创建权限、同文件核验和异常处理规则。

影响：新制度的关键行为依赖模型自行额外阅读，不能作为可验证的 stage 契约执行。

最小修复：在交接契约的 Bookkeeper dispatch-preparation 规则中要求：每个受契约约束的
任务 dispatch 必须在 `Inputs` 明确列出 `agents/roles.md` 的 Task Handoff Evidence Contract，
并在 `Allowed Files` 写出唯一交接路径和 create-only preflight；同时给相关角色增加 scoped
pointer，不复制字段细节。

### BK-002（in-range）：存在但不合格的交接件没有同文件拒收落档路径

事实：Bookkeeper 常规流程要求先在 `BOOKKEEPER_APPEND_ONLY` 标记前计算 SHA-256，再追加
同文件核验区块；但交付同时要求对格式不合格的交接件 fail-closed。若文件已存在但缺失
该标记或结构不合格，无法满足常规 SHA 前提，也未定义如何在同一文件追加拒收依据。现行
“拒收落盘”仍要求记录依据，且契约禁止另建并行核验记录。

影响：异常输入会保持拒收，但拒收依据没有受定义约束的单一落档位置，破坏同文件证据
与 fail-closed 可审计性。

最小修复：定义 malformed-existing handoff 路径：Bookkeeper 绝不改写作者字节；在文件 EOF
只追加显著 `Bookkeeper Verification` 拒收区块，记录 `source_sha256: unavailable`、缺失或
错误前提、可复现检查和 `reported`／blocker 状态。仅在 append marker 存在时计算常规
source SHA-256；文件完全不存在仍走 `SOURCE_REPORT_MISSING`。

## 可复现检查

```text
git rev-parse ed802bc64d5d1476a19b19aa58d773229b24bfa4
git rev-parse e7c0acb81831060369889143072787efe753e3f7
git diff --check ed802bc64d5d1476a19b19aa58d773229b24bfa4 e7c0acb81831060369889143072787efe753e3f7
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json
```
