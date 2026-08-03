# fix-review-2-allowlist-guard-scan — Bookkeeper 核验

核验时间：2026-08-03 10:27 CST

Claude-GLM 回执格式完整。提交
`e99974ad934af5117b0c2385e5545f9861812d5d` 可由 Git 直接解析，且是此前
`3a07f4a87e863d9b2b5b74b92abd09e74dc411b9` 的后代。交付固定范围更新为：
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..e99974ad934af5117b0c2385e5545f9861812d5d`。

## 范围与修复核验

`3a07f4a..e99974a` 恰有两个变动文件，均在 dispatch 的 Allowed Files 内：

- `backend/tests/test_hedge_purity.py`
- `backend/services/hedge_open_live_client.py`

`git diff --check 1a55781..e99974a` 通过。逐词 diff 表明 client 文件的两个 hunk 均位于模块
docstring：补齐五条普通现货/名单 endpoint，并更正为「订单执行仍 default-off；展示 client 由组合根
独立注入，只能 GET 名单」。无运行时代码 hunk。

回执要求的同根因穷举扫描已完整封存于
`evidence/fix-review-2-allowlist-guard-scan.claude-glm.raw.md`：覆盖 `ALLOWLIST`、`get_snapshot`、
`query_leg`、`prepare_attempt`、`_persist_leg_raw`、`build_rows` 六组共享面；除冻结 allowlist 守卫外，
所有命中站点均给出已同步或不适用理由，未发现范围外待修站点。因此满足第二次同根因返工的穷举刹车。

## 独立测试

Bookkeeper 重新运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
1215 passed in 72.32s (0:01:12)

node frontend/self-check.js
全部自检通过
```

测试仅使用本地 fake transport；未读取凭证、未调用 Binance、未启动服务或改变 Start gate。

修复关闭 Opus5 的 F1（冻结 allowlist 守卫失效）与 F2（安全不变量文档失真）。F3 是 Opus5 明确标为
非阻塞的低优先级权威表述问题，仍留给阶段收尾文档复核。本次仍未通过最终 review-2，且须先由
DeepSeek 重跑 review-1。
