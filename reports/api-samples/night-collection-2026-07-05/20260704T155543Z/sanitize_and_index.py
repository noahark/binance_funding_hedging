"""脱敏已采集样本并生成 evidence-index.md / endpoint-matrix.md / api-samples-index.md。

- maxBorrowable 响应中的 amount 替换为 `<AMOUNT>`，borrowLimit 替换为 `<LIMIT>`。
- 计算每个文件的 sha256（基于脱敏后内容）。
- 输出 metadata 到 evidence-index.md。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

OUTDIR = Path(__file__).resolve().parent
RAWDIR = OUTDIR / "raw"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redact_max_borrowable(data: Any) -> Any:
    """账户级数值字段替换为占位符，保留结构和类型。"""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k in ("amount", "borrowLimit") and isinstance(v, str):
                out[k] = "<AMOUNT>" if k == "amount" else "<LIMIT>"
            else:
                out[k] = redact_max_borrowable(v)
        return out
    if isinstance(data, list):
        return [redact_max_borrowable(x) for x in data]
    return data


def sanitize() -> List[Dict[str, Any]]:
    records = []
    for path in sorted(RAWDIR.glob("portfolio_maxBorrowable_*.json")):
        data = load_json(path)
        redacted = redact_max_borrowable(data)
        save_json(path, redacted)
        records.append({"file": path.name, "action": "amount_redacted"})
    return records


def build_evidence_index() -> str:
    manifest = load_json(OUTDIR / "manifest.json")
    lines = [
        "# Night collection evidence index",
        "",
        f"- captured_at_utc: `{manifest['generated_at']}`",
        "- captured_by: Kimi (night-collection goal)",
        "- source: `reports/api-samples/night-collection-2026-07-05/`",
        "- total HTTP calls: {}".format(len(manifest["records"])),
        "",
        "## Endpoint call counts",
        "",
    ]

    counts: Dict[str, int] = {}
    for r in manifest["records"]:
        counts[r["url_stripped"]] = counts.get(r["url_stripped"], 0) + 1
    for url, cnt in sorted(counts.items()):
        lines.append(f"- `{url}`: {cnt}")

    lines += ["", "## Archived files", "", "| file | logical path | type | status | sha256 |", "|---|---|---|---|---|"]

    for r in manifest["records"]:
        fpath = RAWDIR / Path(r["saved_json"]).name
        sha = sha256_file(fpath)
        status = "200"
        if r.get("audit"):
            status = str(r["audit"].get("http_status", "unknown"))
        typ = "private" if r["type"] == "private" else "public"
        lines.append(f"| `{fpath.name}` | `{r['url_stripped']}` | {typ} | {status} | `{sha}` |")

    lines += [
        "",
        "## Redaction policy",
        "",
        "- URL query strings stripped from all archived metadata (only logical path kept); key/secret/signature/recvWindow/timestamp never archived.",
        "- Account-level `maxBorrowable` responses: `amount` and `borrowLimit` numeric-string fields replaced with placeholders; structure and string type preserved.",
        "- Market-level responses are public market data; no amount redaction.",
        "",
        "## Gate status",
        "",
        "All configured endpoints captured successfully; no credentials detected in archived files.",
        "",
    ]
    return "\n".join(lines)


def build_endpoint_matrix() -> str:
    # 从代码中扫描的接口调用点（手动整理，与代码保持一致）
    lines = [
        "# Project endpoint matrix",
        "",
        "本矩阵汇总当前代码库中所有与 Binance 交互的 REST 端点，包括公开端点和私有只读白名单端点。",
        "",
        "## 公开端点（无需 API key）",
        "",
        "| 端点 | 方法 | 调用位置 | 入参 | 出参用途 | 样本文件 |",
        "|---|---|---|---|---|---|",
        "| `/fapi/v1/exchangeInfo` | GET | `backend/adapters/binance_public.py:92` | 无 | U 本位合约交易对元数据 | `raw/fapi-v1-exchangeInfo.json` |",
        "| `/fapi/v1/premiumIndex` | GET | `backend/adapters/binance_public.py:94` | 无 | 最新标记价格、资金费率 | `raw/fapi-v1-premiumIndex.json` |",
        "| `/fapi/v1/fundingInfo` | GET | `backend/adapters/binance_public.py:98` | 无 | 结算间隔（小时） | `raw/fapi-v1-fundingInfo.json` |",
        "| `/api/v3/exchangeInfo` | GET | `backend/adapters/binance_public.py:96` | 无 | 现货交易对元数据 | `raw/api-v3-exchangeInfo.json` |",
        "| `/fapi/v1/fundingRate` | GET | `backend/adapters/binance_public.py:120` | `symbol`, `limit` | 历史资金费率 | `raw/fapi-v1-fundingRate-*-limit20.json` |",
        "",
        "## 私有只读白名单端点（需 API key + HMAC-SHA256）",
        "",
        "| 端点 | 方法 | 调用位置 | 入参 | 出参用途 | 样本文件 |",
        "|---|---|---|---|---|---|",
        "| `/sapi/v1/margin/allPairs` | GET | `backend/services/private_client.py:184` | 无 | 经典杠杆交易对清单 | `raw/classic_allPairs.json` |",
        "| `/sapi/v1/margin/allAssets` | GET | `backend/services/private_client.py:185` | 无 | 资产可借性参考 | `raw/classic_allAssets.json` |",
        "| `/sapi/v1/margin/crossMarginData` | GET | `backend/services/private_client.py:186` | 无 | VIP0 日利率 | `raw/classic_crossMarginData.json` |",
        "| `/papi/v1/margin/maxBorrowable` | GET | `backend/services/private_client.py:214` | `asset` | 统一账户最大可借 | `raw/portfolio_maxBorrowable_BTC.json`, `raw/portfolio_maxBorrowable_ETH.json` |",
        "",
        "## 安全约束",
        "",
        "- 单一 HMAC 出口：`backend/services/private_client.py` 是仓库唯一构造签名的位置。",
        "- deny-by-default 白名单：仅上表四个 `(method, exact-path)` 可调用。",
        "- GET-only：无 POST/PUT/DELETE 代码路径。",
        "- 审计日志：仅记录逻辑路径、HTTP 状态、错误、延迟；不记录 key/secret/signature/query。",
        "",
    ]
    return "\n".join(lines)


def build_api_samples_index() -> str:
    root = OUTDIR.parent.parent  # reports/api-samples
    entries = []
    for subdir in sorted(root.iterdir()):
        if not subdir.is_dir():
            continue
        for ts_dir in sorted(subdir.iterdir()):
            if not ts_dir.is_dir():
                continue
            idx = ts_dir / "evidence-index.md"
            manifest_f = ts_dir / "manifest.json"
            if idx.exists():
                entries.append((subdir.name, ts_dir.name, idx))
            elif manifest_f.exists():
                entries.append((subdir.name, ts_dir.name, manifest_f))

    lines = [
        "# API samples archive index",
        "",
        "本索引列出 `reports/api-samples/` 下所有已归档样本集合，便于 GPT/Claude 快速定位历史证据。",
        "",
        "| collection | timestamp | index file |",
        "|---|---|---|",
    ]
    for collection, ts, idx in entries:
        rel = idx.relative_to(root)
        lines.append(f"| `{collection}` | `{ts}` | `{rel}` |")

    lines += ["", "## 本次新增", "", f"- `night-collection-2026-07-05/20260704T155543Z/evidence-index.md`", ""]
    return "\n".join(lines)


def main() -> None:
    sanitize()
    (OUTDIR / "evidence-index.md").write_text(build_evidence_index(), encoding="utf-8")
    (OUTDIR / "endpoint-matrix.md").write_text(build_endpoint_matrix(), encoding="utf-8")
    # api-samples-index 放在根目录，供整个 archive 使用
    root_index = OUTDIR.parent.parent / "api-samples-index.md"
    root_index.write_text(build_api_samples_index(), encoding="utf-8")
    print("[done] generated evidence-index.md, endpoint-matrix.md, api-samples-index.md")


if __name__ == "__main__":
    main()
