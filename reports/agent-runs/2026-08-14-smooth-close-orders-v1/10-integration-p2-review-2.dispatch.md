Identity:
- task_id: 10-integration-p2-review-2
- target_role: Reviewer
- target_model: opus5
- provider: anthropic
- status_revision: 12
- required_skill: agents/skills/reality-checker.md

Goal:
对平滑平仓 V1 的串联开发交付（P2，交付提交：f95577fc892776e5fe268399a4331d86497c97f9）执行 HIGH_RISK 流程要求的最终 Review-2（产品与风险评审）。
Review-1 已由 gemini-3.1-pro 验证并在技术层面上 ACCEPT。

Allowed Files:
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/10-integration-p2-review-2.handoff.md (创建)

Inputs:
- docs/planning/smooth-close-orders-v1.md
- frontend/index.html (对比 6f6c729..f95577f 的变更)
- backend/app/server.py
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/08-integration-p2.handoff.md
- reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/09-integration-p2-review-1.handoff.md

Acceptance Checks:
1. Review-2 主要核实整体功能是否满足最初设计与用户业务目标，操作体验是否有致命缺陷（如：按钮无反馈、危险动作未提示）。
2. 注意：关于“普通现货账户的可用资金在前端平仓弹窗前被误拦”的问题，已在 Review-1 中定性为 `pre-existing-independent`。Human 已确认该问题将在 Review-2 通过后转入 `PROJECT_STATE.md` 跟进，本轮不再阻塞。
3. 如果未发现其他新引发的重大功能阻断问题，请予以 ACCEPT。

Stop:
完成只读审阅并产出 handoff 后，输出 TASK_RESULT 并停止。交付由 Bookkeeper 最终收口。
