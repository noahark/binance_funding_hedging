"""Curated Binance business-code → official label map for borrow UX.

Sources (public docs, not a live scrape at runtime):

- Portfolio Margin error codes:
  ``developers.binance.com/docs/derivatives/portfolio-margin/error-code``
- Margin trading error codes (shared auth / classic margin codes):
  ``developers.binance.com/docs/margin_trading/error-code``
  (user-facing CN path: zh-CN/.../margin-trading/error-code)

Only codes that matter for this product's signed borrow / recon path are
listed. Lookup is **display-only**: classification still uses the frozen
executor rules. Wire bodies may carry either sign (``51061`` or ``-51061``);
lookup normalizes a single leading ``+``/``-`` before matching.
"""
from __future__ import annotations

from typing import Any, Optional

# key = absolute digit string (no sign). Values are official name + short messages.
_BY_ABS: dict[str, dict[str, str]] = {
    # --- auth / request (common across products) ---
    "1003": {
        "name": "TOO_MANY_REQUESTS",
        "message_en": "Too many requests queued.",
        "message_zh": "请求过多（限频）。",
    },
    "1006": {
        "name": "UNEXPECTED_RESP",
        "message_en": "An unexpected response was received. Execution status unknown.",
        "message_zh": "收到异常响应，执行结果未知。",
    },
    "1007": {
        "name": "TIMEOUT",
        "message_en": "Timeout waiting for backend response. Execution status unknown.",
        "message_zh": "等待后端超时，执行结果未知。",
    },
    "1021": {
        "name": "INVALID_TIMESTAMP",
        "message_en": "Timestamp for this request is outside of the recvWindow.",
        "message_zh": "请求时间戳超出 recvWindow（请对时）。",
    },
    "2014": {
        "name": "BAD_API_KEY_FMT",
        "message_en": "API-key format invalid.",
        "message_zh": "API Key 格式无效。",
    },
    "2015": {
        "name": "REJECTED_MBX_KEY",
        "message_en": "Invalid API-key, IP, or permissions for action.",
        "message_zh": "API Key 无效、IP 不在白名单或权限不足。",
    },
    # --- classic margin borrow family (margin_trading docs) ---
    "3006": {
        "name": "EXCEED_MAX_BORROWABLE",
        "message_en": "Your borrow amount has exceed maximum borrow amount.",
        "message_zh": "借款数量超过最大可借额度。",
    },
    "3007": {
        "name": "HAS_PENDING_TRANSACTION",
        "message_en": "You have pending transaction, please try again later.",
        "message_zh": "存在进行中的借还交易，请稍后重试。",
    },
    "3008": {
        "name": "BORROW_NOT_ALLOWED",
        "message_en": "Borrow not allowed.",
        "message_zh": "当前不允许借币。",
    },
    # --- portfolio margin borrow family (PM docs; live marginLoan) ---
    "51006": {
        "name": "EXCEED_MAX_BORROWABLE",
        "message_en": "Exceeds maximum borrowable amount.",
        "message_zh": "超过最大可借数量。",
    },
    "51007": {
        "name": "HAS_PENDING_TRANSACTION",
        "message_en": "You have pending borrow or repayment, please try again later.",
        "message_zh": "有进行中的借币或还款，请稍后重试。",
    },
    "51014": {
        "name": "ASSET_ADMIN_BAN_BORROW",
        "message_en": "This asset is currently not available for borrowing.",
        "message_zh": "该资产当前禁止借出。",
    },
    "51061": {
        "name": "INSUFFICIENT_LOANABLE_ASSET",
        "message_en": (
            "Due to high borrowing demand, there are currently insufficient "
            "loanable assets. Please adjust your borrow amount or try again later."
        ),
        "message_zh": "可贷资产不足（需求过高/池子借光），请调小数量或稍后再试。",
    },
    "51068": {
        "name": "LIQUIDATION_IN_PROGRESS",
        "message_en": "Unable to trade. Your margin account is currently in liquidation.",
        "message_zh": "账户清算中，暂时无法交易/借币。",
    },
}


def _abs_digits(code: str) -> Optional[str]:
    text = str(code).strip()
    if not text:
        return None
    if text[0] in "+-":
        text = text[1:]
    if not text.isdigit():
        return None
    return text


def lookup_binance_error_code(code: Optional[str]) -> Optional[dict[str, str]]:
    """Return ``{name, message_en, message_zh}`` or ``None`` if unmapped."""
    if code is None:
        return None
    key = _abs_digits(code)
    if key is None:
        return None
    entry = _BY_ABS.get(key)
    if entry is None:
        return None
    return dict(entry)


def business_code_display_fields(code: Optional[str]) -> dict[str, Any]:
    """Additive API fields for a stored business_code (always present keys)."""
    hit = lookup_binance_error_code(code)
    if hit is None:
        return {
            "business_code_name": None,
            "business_code_message": None,
            "business_code_message_zh": None,
        }
    return {
        "business_code_name": hit["name"],
        "business_code_message": hit["message_en"],
        "business_code_message_zh": hit["message_zh"],
    }
