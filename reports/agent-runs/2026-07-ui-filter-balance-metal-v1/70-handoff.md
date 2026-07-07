# 70-handoff

## 当前状态

status=`designing`。已创建 stage 分支与需求/设计草稿；尚未实现。

## 分支

- branch: `stage/2026-07-ui-filter-balance-metal-v1`
- base main sha: `3d3c66e64446d1285a96b4a0e0843e912e4c540e`
- current scope: reports only

## 已完成

- 读取现有前端筛选、余额卡片、资产标签、schema enum 和契约位置。
- 创建 `00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`。
- 明确草稿假设：绝对日费率阈值、null 行不隐藏、METAL 标签、隐私遮蔽。

## 阻塞 / 待确认

1. 低日费率过滤是否按绝对值判断，并且是否排除 `null`。
2. 新选项是否接受 checkbox/toggle，而不是 radio。
3. 贵金属是否只新增标签 `METAL`，还是也要像 bStock 一样禁用负费率借币。
4. 余额展示是否对现货 locked 行保留单独 `冻结:` 行。

## 下一步

用户确认草稿后，进入实现任务书和开发；未确认前不改交付代码。

本地北京时间: 2026-07-08 02:23:15 CST
下一步模型: human
下一步任务: 审阅需求草稿并确认或修改四个待确认点。
