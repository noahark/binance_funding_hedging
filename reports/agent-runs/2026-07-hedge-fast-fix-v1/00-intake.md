# 00-intake：2026-07-hedge-fast-fix-v1

## 触发

Human（2026-07-31）要求开一个 **fast fix stage**：由 Human 连续报告小问题，当前 Grok 会话直接改。

前置对话已确认：

- DB/API 对冲成交数字为 TEXT 全精度，**无 4 位截断**
- 前端 `formatMockPrice` → `toFixed(4)` 仅为展示截断
- `open_basis_rate` 仍为后端占位 `"0"`

## 授权

| 项 | 决定 |
|---|---|
| Bookkeeper | 本会话 Grok（dual-hat：状态维护 + 实现） |
| Implementer | 本会话 Grok（Human 明确「你来改」） |
| 分支 | 不强制 `stage/*`；默认在当前 worktree / main 工作 |
| 下单 / live / 凭据 | **禁止**，除非另有明确 Human 授权 |
| merge / 部署 | 需 Human 另授 |

## 打开时状态

- `ACTIVE.json` → 本 stage
- `base_sha` = 打开时 `main` HEAD
- 等待 Human 第一条 finding
