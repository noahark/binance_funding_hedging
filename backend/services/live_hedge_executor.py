"""Typed live hedge executor (ADR-4 / breakdown §3.7) — injected through the seam.

Wraps :class:`HedgeOpenLiveClient` and maps every transport/exchange observation
into the frozen attempt/leg vocabulary. It is the ONLY path that may POST a real
order, and only when ``APP_HEDGE_EXECUTOR=live`` AND a durable Start gate AND a
fresh preflight context are all handed to it immediately before send.

Per-leg classification is keyed on ACCEPTANCE (a returned ``orderId`` = accepted,
not filled), mirroring :mod:`backend.hedge_open_tasks.domain`. The ordering
follows the recon's timeout/ambiguous reconciliation sequence (recon §3.3 /
breakdown §3.5):

1. transport error / missing status → ``UNKNOWN_QUERYING`` (query by client ID,
   never resend the write POST).
2. 2xx with a valid ``orderId`` → ``ACCEPTED`` (order taken; fill state is
   observational accounting pulled from the response).
3. 2xx without ``orderId`` → ``UNKNOWN_QUERYING`` (malformed 2xx; exchange may
   have accepted without a usable body).
4. 5xx → ``UNKNOWN_QUERYING`` (possibly accepted); HTTP 503 "Service
   Unavailable" / ``-1008`` throttle is a definite failure → ``REJECTED``.
5. 429 / 400+``-1003`` / 418 → ``UNKNOWN_QUERYING`` + ``rate_limited`` (a
   task-local pause signal under amendment 21; not an order rejection).
6. any other definite 4xx → ``REJECTED`` (confirmed not accepted).

A write POST that comes back unknown is queried ONCE by ``origClientOrderId``
inside :meth:`LiveHedgeExecutor.dispatch` as a best-effort resolution; a leg that
is still unknown after that stays ``UNKNOWN_QUERYING`` and is reconciled later by
the task's local worker (query, never resend). Sustained polling to FILLED for
accepted-but-unfilled legs likewise lives in the task's local worker.

This module lives under ``backend/services/`` (it imports the network transport
and the shared signer) and is injected via the service; ``hedge_open_tasks/**``
never imports it (the AST purity guard enforces that).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from ..hedge_open_tasks import domain as D
from ..hedge_open_tasks.executor import (
    AttemptOutcome,
    _client_order_ids,
    build_perp_order_params,
    build_spot_order_params,
)
from .hedge_open_live_client import HedgeHttpResponse, HedgeOpenLiveClient

# Per-leg POST verdict. These alias the domain LEG_* dispatch-state vocabulary so
# the service (which cannot import this services-layer module) matches on domain
# constants rather than a private string contract.
LEG_ACCEPTED = D.LEG_ACCEPTED_OR_QUERYING       # orderId returned — order was taken
LEG_REJECTED = D.LEG_TERMINAL_RECORDED           # confirmed not accepted
LEG_UNKNOWN_QUERYING = D.LEG_UNKNOWN_QUERYING    # no usable verdict — query by client ID

# -1003 TOO_MANY_REQUESTS (recon §4.4); HTTP 400 body code -1003 OR HTTP 429 are
# both rate-limited. 418 is an IP ban (manual re-arm). These are the shared
# exchange cooldown gate, never an order acceptance/rejection.
_RATE_LIMIT_BODY_CODE = "-1003"
_BAN_COOLDOWN_SECONDS = Decimal("300")
# Conservative shared cooldown floor applied when a 429/-1003 surfaces (recon §4.4
# does not pin an exact resume; this is a local fail-safe, not a Binance SLA).
_RATE_LIMIT_COOLDOWN_SECONDS = Decimal("60")

# T1 (10-design §1(c)): the margin/UM asymmetry in fill-figure sourcing is an
# intentional, named rule — NOT an `or` chain. The margin (spot) leg's POST RESULT
# still carries ``cummulativeQuoteQty`` (the 2026-07-14 removal did not touch
# margin); the UM (perp) leg's POST only proves acceptance — its RESULT body no
# longer carries quote/avgPrice, so the authoritative figures come from the
# order-detail GET (inline confirm here, drain in the worker). When Binance next
# changes one product's response, the edit is to THIS named rule, not a stray
# take-value site. ``leg`` ("spot" | "perp") is the product discriminator.
FILL_FIGURES_SOURCE = {
    "spot": "post_response",        # margin: POST RESULT body carries cummulativeQuoteQty
    "perp": "order_detail_query",   # UM: POST proves acceptance only; figures via GET
}


def _leg_product(leg: str, spot_route: str) -> str:
    """The endpoint product a leg speaks (design §4). The perp leg is always UM;
    the spot leg is ``PRODUCT_SPOT`` on a ``regular_spot`` route (``/api/v3/order``
    on api.binance.com) and ``PRODUCT_MARGIN`` on the PAPI margin route. The
    product drives per-leg business-code classification so a regular-spot leg
    never inherits margin's 51169 collateral-cap rule."""
    if leg == "perp":
        return D.PRODUCT_UM
    return D.PRODUCT_SPOT if spot_route == D.SPOT_ROUTE_REGULAR_SPOT else D.PRODUCT_MARGIN


def _quote_decimal(raw) -> Optional[str]:
    """Coerce one fill-figure field to a decimal string, or ``None`` when the
    response did not carry it (T1 §1(d): ``None`` = unknown, never a coerced 0)."""
    if raw is None or isinstance(raw, bool) or raw == "":
        return None
    try:
        text = format(Decimal(str(raw)), "f")
    except (InvalidOperation, ValueError, TypeError):
        return None
    return text or None


def _avg_price_decimal(raw) -> Optional[str]:
    """avgPrice is informational; any **numeric zero** or missing/unparseable
    value -> ``None``; a non-zero value passes through :func:`_quote_decimal`
    verbatim (no formatting change).

    Numeric-zero detection (R2-Rerun-F1): Binance USDⓈ-M returns
    ``avgPrice="0.00000"`` for an accepted-but-unfilled order, and ``"0.00000"``
    is not equal to the literal ``"0"`` the old ``raw in (..., "0", ...)`` check
    tested for — so it slipped through and displayed as a real price. ``Decimal``
    compares by value, so ``Decimal("0.00000") == 0`` and ``Decimal("0E-8") == 0``
    both catch every zero spelling. A zero avgPrice is never a real fill price.

    Distinct from :func:`_quote_decimal`: a quote ``"0"`` is a REAL zero fill
    (kept), whereas an avgPrice zero is unknown (dropped). Do not unify them.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if value == 0:
        return None
    return _quote_decimal(raw)


def _post_figures(body, leg: str) -> tuple[str, Optional[str], Optional[str]]:
    """Fill figures from a POST RESULT body, by product (T1 §1(c)).

    Returns ``(executed_qty, cumulative_quote, avg_price)``. The margin leg reads
    ``cummulativeQuoteQty`` authoritatively from the POST; the UM leg's POST only
    proves acceptance, so its quote/avg_price are ``None`` here (the inline confirm
    GET supplies them). ``executed_qty`` keeps the ``"0"`` default — an accepted
    not-yet-filled leg genuinely has zero executed qty (a true value).
    """
    if not isinstance(body, dict):
        return ("0", None, None)
    executed = _decimal_str(body.get("executedQty"))
    if leg == "spot":
        quote = _quote_decimal(body.get("cummulativeQuoteQty"))
    else:  # UM POST is acceptance-only (2026-07-14 RESULT dropped quote/avgPrice)
        quote = None
    avg = _avg_price_decimal(body.get("avgPrice"))
    return (executed, quote, avg)


def _query_figures(body, leg: str) -> tuple[str, Optional[str], Optional[str]]:
    """Fill figures from an order-detail GET body, by product (T1 §1(c)).

    margin reads ``cummulativeQuoteQty``; UM reads ``cumQuote`` (falling back to the
    ``cummulativeQuoteQty`` spelling for compatibility) + ``avgPrice``. The
    response-not-carried case is ``None`` (NULL), not a coerced 0.
    """
    if not isinstance(body, dict):
        return ("0", None, None)
    executed = _decimal_str(body.get("executedQty"))
    if leg == "spot":
        quote = _quote_decimal(body.get("cummulativeQuoteQty"))
    else:  # UM order detail: cumQuote (Binance UM spelling), cummulativeQuoteQty fallback
        raw = body.get("cumQuote")
        if raw in (None, ""):
            raw = body.get("cummulativeQuoteQty")
        quote = _quote_decimal(raw)
    avg = _avg_price_decimal(body.get("avgPrice"))
    return (executed, quote, avg)


def _business_code(response: HedgeHttpResponse) -> Optional[str]:
    body = response.body
    if isinstance(body, dict):
        code = body.get("code")
        if code is not None:
            return str(code)
    return None


def _business_msg(response: HedgeHttpResponse) -> Optional[str]:
    body = response.body
    if isinstance(body, dict):
        msg = body.get("msg")
        return str(msg) if msg is not None else None
    return None


def _raw_response_dict(response: HedgeHttpResponse) -> dict:
    """Build the sanitized raw-response dict carried on :class:`LegDispatch` for
    T3 persistence (10-design §3). Drawn from the exchange RESPONSE only —
    http_status / transport_error / business code+msg / raw_body. By construction
    no request parameter, signature, or API key is present (``HedgeHttpResponse``
    retains none of them), so the dict is safe to persist verbatim."""
    return {
        "http_status": response.http_status,
        "transport_error": response.transport_error,
        "code": _business_code(response),
        "msg": _business_msg(response),
        "body": response.raw_body,
    }


def _normalize_order_id(value) -> Optional[str]:
    """Arbitrary-precision-positive-integer orderId -> canonical string; never float.

    ``orderId`` is documented int64; JSON may deliver it as int or numeric string.
    Anything non-positive, non-integer, empty, or unparseable is rejected so a
    malformed 2xx never counts as accepted.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError):
            return None
        if not parsed.is_finite() or parsed <= 0:
            return None
        if parsed != parsed.to_integral_value():
            return None
        return format(parsed.to_integral_value(), "f")
    return None


def _is_rate_limited(response: HedgeHttpResponse) -> bool:
    if response.transport_error is not None or response.http_status is None:
        return False
    status = response.http_status
    return status == 429 or status == 418 or (
        status == 400 and _business_code(response) == _RATE_LIMIT_BODY_CODE
    )


def _is_throttle_failure(response: HedgeHttpResponse) -> bool:
    """HTTP 503 'Service Unavailable' / -1008 = definite failure (recon §3.3 #8/#9).

    Distinguished from HTTP 503 'Unknown error' (#7, state unknown → query): only
    a 503 whose body carries -1008, or a body/msg literally naming 'Service
    Unavailable', is treated as a confirmed failure. Any other 5xx stays unknown.
    """
    if response.http_status != 503:
        return False
    if _business_code(response) == "-1008":
        return True
    msg = (_business_msg(response) or "").lower()
    return "service unavailable" in msg


def _decimal_str(value, default: str = "0") -> str:
    if value is None or isinstance(value, bool):
        return default
    try:
        text = format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError, TypeError):
        return default
    return text if text else default


@dataclass(frozen=True)
class LegDispatch:
    """One leg's POST verdict + the observational fill figures from the response.

    ``error_category`` in {None, "auth", "fatal", "insufficient_funds",
    "collateral_cap", "unclassified", "absent"} classifies the exchange response
    for the error matrix (amendment 21 manual-pause isolation), produced by
    :func:`domain.classify_exchange_code`: "auth" = auth/signature/timestamp/
    permission ambiguity -> stay UNKNOWN and query by client ID (never resend);
    "insufficient_funds" = a CONFIRMED insufficient balance/margin/available-
    quantity fact (-2019/-3041 unambiguous; -2010 only when its message confirms
    it) -> pauses THIS task only (worker exits, manual recovery); "fatal" = the
    remaining hard facts (filter/min-notional/symbol/mode, and an unconfirmed
    -2010) -> stops the task; "collateral_cap" = 51169, the asset is above
    Binance's platform collateral cap -> pauses THIS task only; "unclassified" =
    a business code was present but no rule matched (a counted non-fatal
    failure); "absent" = the order was never accepted (query-path 404/-2013);
    ``None`` = the response carried no business code at all. "unclassified" and
    ``None`` stay distinct (the defect this stage fixes collapsed them).
    ``error_code`` is the exchange business code when available.
    ``retry_after_seconds`` carries a stated exchange wait (429/Retry-After) so
    the task-local worker pauses THIS task without changing any other task's
    state (amendment 21).
    """

    leg: str  # "spot" | "perp"
    dispatch_state: str  # LEG_ACCEPTED | LEG_REJECTED | LEG_UNKNOWN_QUERYING
    order_id: Optional[str]
    exchange_status: Optional[str]  # FILLED | NEW | PARTIALLY_FILLED | REJECTED | EXPIRED | UNKNOWN
    executed_qty: str
    cumulative_quote: Optional[str]
    avg_price: Optional[str]
    rate_limited: bool = False
    error_code: Optional[str] = None
    error_category: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    raw_response: Optional[dict] = None  # T3 (10-design §3): sanitized POST exchange response for raw persistence (source=order_post)
    confirm_raw_response: Optional[dict] = None  # T1+T3 (§1(b)/§3(b)): sanitized UM inline-confirm GET response (source=order_confirm)
    query_raw_response: Optional[dict] = None  # T3 (§3): sanitized order-detail GET body from the UNKNOWN-POST immediate best-effort query (source=order_query) — the response that decided the leg's fate when the POST was inconclusive; distinct from raw_response (POST) and confirm_raw_response (UM accepted confirm)


@dataclass(frozen=True)
class LiveAttemptDispatch:
    """Both legs' dispatch verdicts for one attempt + the would-send record."""

    attempt_id: str
    spot: LegDispatch
    perp: LegDispatch
    record_payload: dict
    rate_limited: bool  # any leg surfaced a 429/-1003/418 -> task-local worker pauses THIS task (amendment 21)
    retry_after_seconds: Optional[int]  # stated exchange wait (amendment 21 rate-limit pause)


def _empty_dispatch(
    leg: str, dispatch_state: str, *, rate_limited: bool = False,
    error_code: Optional[str] = None, error_category: Optional[str] = None,
    retry_after_seconds: Optional[int] = None, raw: Optional[dict] = None,
) -> LegDispatch:
    return LegDispatch(
        leg=leg,
        dispatch_state=dispatch_state,
        order_id=None,
        exchange_status=None,
        executed_qty="0",
        cumulative_quote=None,
        avg_price=None,
        rate_limited=rate_limited,
        error_code=error_code,
        error_category=error_category,
        retry_after_seconds=retry_after_seconds,
        raw_response=raw,
    )


def classify_leg_response(
    response: HedgeHttpResponse, leg: str, product: Optional[str] = None
) -> LegDispatch:
    """Map one leg's POST response to a dispatch verdict (recon §3.3 + amendment
    §Error handling).

    ``product`` is the leg's endpoint product (:data:`domain.PRODUCT_MARGIN`,
    :data:`domain.PRODUCT_UM`, or :data:`domain.PRODUCT_SPOT` for a regular-spot
    leg); the live executor always passes it explicitly (a regular-spot leg gets
    ``PRODUCT_SPOT`` so the per-product business-code layer keeps it OFF the
    margin 51169 collateral-cap rule — design §4, ``/api/v3/order`` cannot return
    that PAPI margin code). When omitted, the legacy PAPI inference
    (spot→margin, perp→um) applies for direct callers."""
    if product is None:
        product = D.PRODUCT_MARGIN if leg == "spot" else D.PRODUCT_UM
    # T3 (10-design §3): capture every POST interaction's sanitized response —
    # including transport failures, rate limits, 5xx and rejections — so the next
    # 51169 is explainable from the DB alone. Built once, threaded through every
    # return path; persistence is the service's concern (after the business write).
    raw = _raw_response_dict(response)
    if response.transport_error is not None or response.http_status is None:
        return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)
    if _is_rate_limited(response):
        # 429 / -1003 / 418: process-wide write delay, never a business verdict.
        return _empty_dispatch(
            leg, LEG_UNKNOWN_QUERYING, rate_limited=True,
            retry_after_seconds=response.retry_after_seconds, raw=raw,
        )
    status = response.http_status
    # 5xx: possibly accepted, EXCEPT a confirmed 503 throttle failure.
    if 500 <= status < 600:
        if status == 503 and _is_throttle_failure(response):
            return _empty_dispatch(leg, LEG_REJECTED, raw=raw)
        return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)
    # 2xx: a valid orderId is the only acceptance proof.
    if 200 <= status < 300:
        order_id = None
        exchange_status = None
        if isinstance(response.body, dict):
            order_id = _normalize_order_id(response.body.get("orderId"))
            exchange_status = response.body.get("status")
        if order_id is None:
            return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)
        # T1 §1(c): fill figures come from the POST only for the margin (spot) leg;
        # the UM (perp) POST proves acceptance alone, so its quote/avg_price stay
        # None here and are filled by the inline confirm GET in _send_one_leg.
        executed_qty, cumulative_quote, avg_price = _post_figures(response.body, leg)
        return LegDispatch(
            leg=leg,
            dispatch_state=LEG_ACCEPTED,
            order_id=order_id,
            exchange_status=str(exchange_status) if exchange_status is not None else D.LEG_NEW,
            executed_qty=executed_qty,
            cumulative_quote=cumulative_quote,
            avg_price=avg_price,
            raw_response=raw,
        )
    # Definite 4xx (non-rate-limit). The amendment error matrix splits these via
    # domain.classify_exchange_code (two-layer: shared gateway/business + per-
    # product). auth/signature/timestamp/permission ambiguity -> stay UNKNOWN and
    # query by client ID (never resend, amendment row 5); every other definite
    # rejection -> confirmed not accepted (REJECTED), with error_category carrying
    # the precise verdict: fatal (rows 1–2 stop), insufficient_funds /
    # collateral_cap (task-local pause), unclassified (a present-but-unrecognized
    # code, a counted non-fatal failure), or None (the body carried no business
    # code at all — still a rejected leg). NULL now means exclusively "no code";
    # "unclassified" means "a code we could not classify" — they must stay
    # distinguishable (the defect this stage fixes).
    if 400 <= status < 500:
        code = _business_code(response)
        category = D.classify_exchange_code(product, code, _business_msg(response))
        if category == D.ERROR_CATEGORY_AUTH:
            return _empty_dispatch(
                leg, LEG_UNKNOWN_QUERYING, error_code=code, error_category=category,
                raw=raw,
            )
        return _empty_dispatch(
            leg, LEG_REJECTED, error_code=code, error_category=category, raw=raw,
        )
    return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)


def classify_query_response(
    response: HedgeHttpResponse, leg: str, product: Optional[str] = None
) -> Optional[LegDispatch]:
    """Map a GET origClientOrderId query to a leg verdict, or ``None`` if still
    inconclusive (keep querying — never resend). ``product`` selects the
    per-product business-code layer (regular-spot legs pass ``PRODUCT_SPOT`` so
    they never inherit margin's 51169 rule); when omitted the legacy PAPI
    inference (spot→margin, perp→um) applies.

    recon §3.3: FILLED → accepted+filled; NEW/PARTIALLY_FILLED → accepted but
    still filling (non-terminal); 404/absent → never accepted (rejected).

    R2-F2 (user authorization 28 §2.2): a 2xx missing a valid orderId is NOT a
    confirmed absent signal — it stays UNKNOWN_QUERYING (a malformed body must
    never reject a possibly-accepted order; only an explicit 404 / Binance -2013
    confirms absent). A rate-limited query (429 / -1003 / 418) returns a TYPED
    rate-limit signal (UNKNOWN_QUERYING + rate_limited=True) so the task's worker
    observes the throttle, pauses THIS task, keeps the pending leg, and exits for
    manual recovery — never resends. A transport-failed or 5xx query stays
    ``None`` (genuinely inconclusive, keep querying).
    """
    # T3 (10-design §3): capture the sanitized query response on every verdict
    # path (a None return is a genuinely inconclusive retry — no verdict, no row).
    raw = _raw_response_dict(response)
    if response.transport_error is not None or response.http_status is None:
        return None
    if _is_rate_limited(response):
        # R2-F2: surface the throttle as a typed signal so the worker can pause
        # THIS task and keep the pending leg; the query is NOT inconclusive.
        return _empty_dispatch(
            leg, LEG_UNKNOWN_QUERYING, rate_limited=True,
            retry_after_seconds=response.retry_after_seconds, raw=raw,
        )
    status = response.http_status
    if status >= 500:
        return None  # query itself failed ambiguously — keep querying
    if 400 <= status < 500:
        # Amendment row 5: ONLY an explicit order-absent signal confirms the
        # order was never accepted. A literal 404 or Binance -2013 (order does
        # not exist) is the authoritative absent signal. Auth/signature/
        # timestamp/permission codes, and any other ambiguous 4xx, stay
        # inconclusive (return None -> keep querying by client ID, never resend).
        code = _business_code(response)
        if status == 404 or code == "-2013":
            return _empty_dispatch(
                leg, LEG_REJECTED, error_code=code or "http_404", error_category="absent",
                raw=raw,
            )
        return None
    if 200 <= status < 300 and isinstance(response.body, dict):
        order_id = _normalize_order_id(response.body.get("orderId"))
        exchange_status = response.body.get("status")
        if order_id is None:
            # R2-F2: no orderId on a 2xx query is NOT a confirmed absent signal
            # — only an explicit 404 / -2013 is. A malformed 2xx stays UNKNOWN so
            # the worker keeps querying by client ID (never resends, never
            # rejects a possibly-accepted order as absent).
            return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING, raw=raw)
        # T1 §1(c): order-detail GET figures, by product (margin reads
        # cummulativeQuoteQty; UM reads cumQuote with a cummulativeQuoteQty
        # fallback). A field the response did not carry is None (NULL), not a 0.
        executed_qty, cumulative_quote, avg_price = _query_figures(response.body, leg)
        # NEW/PARTIALLY_FILLED → accepted, still filling (non-terminal downstream).
        # FILLED/CANCELED/EXPIRED/REJECTED carry their own terminal meaning; the
        # service maps REJECTED/CANCELED/EXPIRED to a confirmed-not-filled leg.
        return LegDispatch(
            leg=leg,
            dispatch_state=LEG_ACCEPTED,
            order_id=order_id,
            exchange_status=str(exchange_status) if exchange_status is not None else D.LEG_NEW,
            executed_qty=executed_qty,
            cumulative_quote=cumulative_quote,
            avg_price=avg_price,
            raw_response=raw,
        )
    return None


def dispatch_to_outcome(
    attempt_id: str, spot: LegDispatch, perp: LegDispatch, record_payload: dict,
    ts_us: int,
) -> AttemptOutcome:
    """Build an :class:`AttemptOutcome` from two resolved leg dispatches.

    Used when both legs already carry a definite acceptance verdict (ACCEPTED or
    REJECTED). The scheduler counter keys off ``order_id`` presence
    (:func:`domain.classify_attempt`); the leg dicts carry the observational fill
    figures for accounting. ``ts_us`` is the settlement wall clock — the live
    exposure timestamp (10-design §4(a)), mandatory (no safe default).
    """
    spot_leg = {
        "status": _exchange_status_for_outcome(spot),
        "filled_qty": spot.executed_qty,
        "avg_price": spot.avg_price,
        "order_id": spot.order_id,
        "client_order_id": None,
    }
    perp_leg = {
        "status": _exchange_status_for_outcome(perp),
        "filled_qty": perp.executed_qty,
        "avg_price": perp.avg_price,
        "order_id": perp.order_id,
        "client_order_id": None,
    }
    category = D.classify_attempt(spot_leg, perp_leg)
    exposure = (
        D.build_leg_exposure(spot_leg, perp_leg, ts_us) if category == D.ATTEMPT_SINGLE_LEG_EXPOSURE else None
    )
    return AttemptOutcome(
        attempt_id=attempt_id,
        category=category,
        spot=spot_leg,
        perp=perp_leg,
        record_payload=record_payload,
        exposure=exposure,
    )


def _exchange_status_for_outcome(leg: LegDispatch) -> str:
    """Map a dispatch's exchange status to the domain LEG_* accounting status.

    An accepted leg that is NEW/PARTIALLY_FILLED is still 'accepted' (orderId
    present); for accounting it records its executed qty. A rejected leg maps to
    LEG_REJECTED. FILLED passes through.
    """
    if leg.dispatch_state == LEG_REJECTED:
        return D.LEG_REJECTED
    return leg.exchange_status or D.LEG_NEW


def leg_is_terminal_fill(leg: LegDispatch) -> bool:
    """A leg is a terminal fill when confirmed rejected, or accepted+FILLED with
    authoritative figures (T1 §1(b)).

    A UM (perp) FILLED leg whose authoritative quote is still unknown (the inline
    confirm GET came back inconclusive) is NOT terminal — it stays for the
    worker's drain. The margin (spot) leg reads its quote from the POST RESULT, so
    an accepted+FILLED spot leg is terminal as before."""
    if leg.dispatch_state == LEG_REJECTED:
        return True
    if leg.dispatch_state == LEG_ACCEPTED:
        if leg.exchange_status != D.LEG_FILLED:
            return False
        # T1 §1(b): a UM FILLED leg needs its authoritative quote known to settle.
        if leg.leg != "spot" and leg.cumulative_quote is None:
            return False
        return True
    return False


class LiveHedgeExecutor:
    """Production executor over the exact-path PAPI order client.

    ``dispatch`` submits both legs of one attempt concurrently (frozen §6.3.4),
    classifies each response on acceptance, and best-effort queries any unknown
    leg once by ``origClientOrderId`` (never resends). Legs still unknown after
    that stay ``UNKNOWN_QUERYING`` for the service's reconcile pass.
    """

    def __init__(self, client: HedgeOpenLiveClient, *, now_ms: Callable[[], int]):
        self._client = client
        self._now_ms = now_ms

    @property
    def credentials_present(self) -> bool:
        return self._client.credentials_present

    def _send_one_leg(
        self, leg: str, params: dict, symbol: str, client_order_id: str,
        spot_route: str,
    ) -> LegDispatch:
        """POST one leg, classify, and best-effort query once if unknown.

        ``spot_route`` selects the spot leg's endpoint + product: ``regular_spot``
        -> ``/api/v3/order`` (api.binance.com, ``PRODUCT_SPOT``); ``papi_margin``
        -> the PAPI margin endpoint (``PRODUCT_MARGIN``). The perp leg is always
        UM and ignores ``spot_route``. The query path follows the SAME endpoint
        the POST used (the leg row ``endpoint`` is the authority — design §4)."""
        if not self._client.credentials_present:
            return _empty_dispatch(leg, LEG_UNKNOWN_QUERYING)
        product = _leg_product(leg, spot_route)
        if leg == "spot":
            if spot_route == D.SPOT_ROUTE_REGULAR_SPOT:
                response = self._client.post_spot_order(params, timestamp_ms=self._now_ms())
                querier = self._client.query_spot_order
            else:
                response = self._client.post_margin_order(params, timestamp_ms=self._now_ms())
                querier = self._client.query_margin_order
        else:
            response = self._client.post_um_order(params, timestamp_ms=self._now_ms())
            querier = self._client.query_um_order
        verdict = classify_leg_response(response, leg, product)
        # T1 §1(b): a UM (perp) leg whose POST proved acceptance still lacks
        # authoritative fill figures — confirm them via the order-detail GET now.
        if leg != "spot" and verdict.dispatch_state == LEG_ACCEPTED:
            verdict = self._confirm_um_figures(symbol, client_order_id, verdict)
        if verdict.dispatch_state == LEG_UNKNOWN_QUERYING:
            query_response = querier(symbol, client_order_id, timestamp_ms=self._now_ms())
            resolved = classify_query_response(query_response, leg, product)
            if resolved is not None:
                # R2-F2: preserve the rate-limited signal + wait from EITHER the
                # POST/confirm or the best-effort query (a query-time 429 must
                # surface even when the POST verdict was not itself throttled), and
                # carry the query's resolved acceptance / error classification.
                # The POST raw is preserved on raw_response (T3 §3(b) POST capture);
                # any inline-confirm raw rides on confirm_raw_response. The GET that
                # just resolved this leg rides on query_raw_response (T3 §3) so it is
                # persisted separately as source=order_query — never merged onto or
                # over the POST (the GET is the only record of what happened when the
                # POST was inconclusive).
                return LegDispatch(
                    leg=resolved.leg,
                    dispatch_state=resolved.dispatch_state,
                    order_id=resolved.order_id,
                    exchange_status=resolved.exchange_status,
                    executed_qty=resolved.executed_qty,
                    cumulative_quote=resolved.cumulative_quote,
                    avg_price=resolved.avg_price,
                    rate_limited=verdict.rate_limited or resolved.rate_limited,
                    error_code=resolved.error_code,
                    error_category=resolved.error_category,
                    retry_after_seconds=(
                        verdict.retry_after_seconds or resolved.retry_after_seconds
                    ),
                    raw_response=verdict.raw_response,
                    confirm_raw_response=verdict.confirm_raw_response,
                    query_raw_response=resolved.raw_response,
                )
        return verdict

    def _confirm_um_figures(
        self, symbol: str, client_order_id: str, post_verdict: LegDispatch,
    ) -> LegDispatch:
        """T1 §1(b): a UM (perp) leg whose POST proved acceptance (orderId) still
        lacks authoritative fill figures — the 2026-07-14 UM RESULT body dropped
        cumQuote/avgPrice. Immediately confirm via the order-detail GET and merge.

        A confirm that returns an accepted verdict WITH a known quote merges the
        authoritative figures (executed_qty / cumulative_quote / avg_price / a
        refined status). Any other confirm outcome — inconclusive (timeout / 5xx),
        a malformed 2xx, or even a literal 404/-2013 (a POST-just-accepted order
        404-ing is eventual-consistency noise, NOT a real absent signal) — leaves
        the leg ACCEPTED with ``cumulative_quote=None`` so it is non-terminal and
        the worker drains it next round (query, never resend). The confirm GET's
        sanitized response rides on ``confirm_raw_response`` for T3 capture; the
        POST raw on ``raw_response`` is preserved either way.
        """
        query_response = self._client.query_um_order(
            symbol, client_order_id, timestamp_ms=self._now_ms(),
        )
        confirmed = classify_query_response(query_response, "perp", D.PRODUCT_UM)
        confirm_raw = _raw_response_dict(query_response)
        rate_limited = post_verdict.rate_limited or (
            confirmed.rate_limited if confirmed is not None else False
        )
        retry_after = post_verdict.retry_after_seconds or (
            confirmed.retry_after_seconds if confirmed is not None else None
        )
        if (
            confirmed is not None
            and confirmed.dispatch_state == LEG_ACCEPTED
            and confirmed.cumulative_quote is not None
        ):
            # Authoritative figures confirmed: merge them onto the POST acceptance.
            return LegDispatch(
                leg=post_verdict.leg,
                dispatch_state=post_verdict.dispatch_state,
                order_id=post_verdict.order_id,
                exchange_status=confirmed.exchange_status or post_verdict.exchange_status,
                executed_qty=confirmed.executed_qty,
                cumulative_quote=confirmed.cumulative_quote,
                avg_price=confirmed.avg_price,
                rate_limited=rate_limited,
                error_code=post_verdict.error_code,
                error_category=post_verdict.error_category,
                retry_after_seconds=retry_after,
                raw_response=post_verdict.raw_response,
                confirm_raw_response=confirm_raw,
            )
        # Confirm inconclusive / no figures: keep POST acceptance, quote unknown,
        # leg non-terminal (drain later). Never coerce the missing figure to 0.
        return LegDispatch(
            leg=post_verdict.leg,
            dispatch_state=post_verdict.dispatch_state,
            order_id=post_verdict.order_id,
            exchange_status=post_verdict.exchange_status,
            executed_qty=post_verdict.executed_qty,
            cumulative_quote=None,
            avg_price=None,
            rate_limited=rate_limited,
            error_code=post_verdict.error_code,
            error_category=post_verdict.error_category,
            retry_after_seconds=retry_after,
            raw_response=post_verdict.raw_response,
            confirm_raw_response=confirm_raw,
        )

    def dispatch(self, ctx) -> LiveAttemptDispatch:
        """Submit both legs concurrently and return their dispatch verdicts.

        Concurrency is within the pair (frozen §6.3.4): the two legs are sent on
        two threads and neither waits on the other's result. Each thread
        classifies its own response and best-effort queries once if unknown.
        """
        actions = D.direction_to_leg_actions(
            ctx.direction, ctx.position_side_mode or D.POS_MODE_BOTH
        )
        send_qty = ctx.q_common if ctx.q_common is not None else ctx.single_amount
        spot_cid, perp_cid = _client_order_ids(ctx.attempt_id)
        spot_symbol = D.spot_order_symbol(ctx.coin, ctx.preflight_snapshot)
        spot_route = (ctx.preflight_snapshot or {}).get(
            "spot_route", D.SPOT_ROUTE_PAPI_MARGIN
        )
        if spot_route == D.SPOT_ROUTE_REGULAR_SPOT:
            spot_params = D.build_regular_spot_order_params(
                spot_symbol, actions, send_qty, spot_cid
            )
        else:
            spot_params = build_spot_order_params(spot_symbol, actions, send_qty, spot_cid)
        perp_params = build_perp_order_params(ctx.coin, actions, send_qty, perp_cid)
        record_payload = {
            "transport": "live",
            "posted": True,
            "spot_order_params": spot_params,
            "perp_order_params": perp_params,
            "client_ids": {"spot": spot_cid, "perp": perp_cid},
            "q_common": str(ctx.q_common) if ctx.q_common is not None else None,
            "send_quantity": str(send_qty),
            "filter_versions": ctx.filter_versions,
            "preflight_snapshot": ctx.preflight_snapshot,
        }
        outcomes: dict[str, LegDispatch] = {}
        errors: dict[str, BaseException] = {}

        def _run(leg: str, params: dict, cid: str) -> None:
            try:
                symbol = spot_symbol if leg == "spot" else ctx.coin
                outcomes[leg] = self._send_one_leg(leg, params, symbol, cid, spot_route)
            except Exception as exc:  # containment: a leg send failure is queryable, not fatal
                errors[leg] = exc

        threads = [
            threading.Thread(target=_run, args=("spot", spot_params, spot_cid), name="hgo-leg-spot"),
            threading.Thread(target=_run, args=("perp", perp_params, perp_cid), name="hgo-leg-perp"),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        spot = outcomes.get("spot") or _error_leg("spot", errors.get("spot"))
        perp = outcomes.get("perp") or _error_leg("perp", errors.get("perp"))
        rate_limited = spot.rate_limited or perp.rate_limited
        # The stated exchange wait (Retry-After) for a 429/-1003/418: the longest
        # of the two legs governs the process-wide write delay (amendment row 6).
        waits = [w for w in (spot.retry_after_seconds, perp.retry_after_seconds) if w]
        retry_after = max(waits) if waits else None
        return LiveAttemptDispatch(
            attempt_id=ctx.attempt_id,
            spot=spot,
            perp=perp,
            record_payload=record_payload,
            rate_limited=rate_limited,
            retry_after_seconds=retry_after,
        )

    def query_leg(
        self, leg: str, symbol: str, client_order_id: str, endpoint: str,
    ) -> Optional[LegDispatch]:
        """Reconcile pass: query one non-terminal leg by ``origClientOrderId``.

        Returns ``None`` when the query is itself inconclusive (keep querying);
        a definite verdict (accepted / confirmed-absent) otherwise. Never resends
        the write POST.

        ``endpoint`` is the leg row's persisted endpoint (design §4: the SOLE
        authority for which query path a leg uses — never re-derived from leg name
        or task-level route). A spot leg whose endpoint is the regular-spot
        ``/api/v3/order`` queries via the spot querier with ``PRODUCT_SPOT``; a
        PAPI margin endpoint uses the margin querier; the perp leg is always UM.
        """
        if not self._client.credentials_present:
            return None
        if leg == "perp":
            querier = self._client.query_um_order
            product = D.PRODUCT_UM
        elif endpoint == D.REGULAR_SPOT_ORDER_PATH:
            querier = self._client.query_spot_order
            product = D.PRODUCT_SPOT
        else:
            querier = self._client.query_margin_order
            product = D.PRODUCT_MARGIN
        response = querier(symbol, client_order_id, timestamp_ms=self._now_ms())
        return classify_query_response(response, leg, product)


def _error_leg(leg: str, exc: Optional[BaseException]) -> LegDispatch:
    """A leg whose send/thread raised maps to UNKNOWN_QUERYING (query, not fail)."""
    return LegDispatch(
        leg=leg,
        dispatch_state=LEG_UNKNOWN_QUERYING,
        order_id=None,
        exchange_status=None,
        executed_qty="0",
        cumulative_quote=None,
        avg_price=None,
        rate_limited=False,
    )
