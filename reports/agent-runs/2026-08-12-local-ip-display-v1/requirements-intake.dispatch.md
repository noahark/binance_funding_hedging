# 本机 IP 展示需求澄清 dispatch — Codex / GPT-5

## Identity

- task_id: `local-ip-display-requirements-intake`
- target_role: `Planner`
- target_model: `codex / GPT-5`
- provider: `openai`
- status_revision: `1`
- required_skill: `none`

## Goal

与 Human 明确「资金费率对冲工作台右侧展示本机 IP」的最小交付边界：准确位置、IP 的来源和更新时机、不可用时的界面文案，以及是否只显示内网/本机地址或也需要公网出口地址。此任务不实现。

## Allowed Files

- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/requirements-intake.md`

## Inputs

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Planner` 小节

## Acceptance Checks

1. Human 明确展示位置与希望看到的地址类型。
2. Human 确认是否允许浏览器请求外部服务取得公网出口 IP；未确认时不得假定允许。
3. Human 确认刷新方式与不可用时的展示口径。

## Stop

只记录已确认需求并准备后续最小实现范围；不得修改产品代码、启动服务、访问交易所、读取凭据、提交、推送、合并、部署或执行任何外部副作用。
