# R4 范围偏差记录：分页游标纯函数

## 事实

56 号后端分页修复包的最窄允许文件列表列出了 `service.py`、`store.py`、
`server.py` 和相关测试；实际实现还修改了：

```text
backend/hedge_open_tasks/domain.py
```

新增内容是 `entries_cursor` 的纯编解码与校验常量。它把统一分页排序键
`(ts_us, rank, row_id)` 写成不透明字符串，并在读取时拒绝非法 rank/格式。

## 判定

这是已解释的、必要的范围偏差：该函数没有 SQLite、网络、签名、凭据、订单参数或
交易业务副作用；把它放入 `domain.py` 保持了该项目既有“纯领域函数由 service/store 复用”
的边界。它只服务于 17 号兼容修正的分页功能，未扩大到任何实盘或风险逻辑。

不为了形式把纯函数机械搬回 service；这会降低复用和可测试性。相应地，后端 Review-1
必须显式核对该函数的编码、解码和非法输入 fail-closed（失败即拒绝）行为。58 号包已经
要求审查实际 diff、domain 和分页安全性，因此无需改写其已提交 prompt。

## 影响

- 没有新增真实网络、凭据访问、签名逻辑、API 路由或下单行为；
- 882 项后端测试与 63 项直接相关回归均已通过；
- 该偏差不消除或降低任何 Review-1 / Review-2 门禁。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/20-r4-scope-deviation-domain-cursor.md
本地北京时间: 2026-07-24 21:26:56 CST
下一步模型: human operator
下一步任务: run packet 58; its backend reviewer must inspect this recorded scope deviation against the actual diff
