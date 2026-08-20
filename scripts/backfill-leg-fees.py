#!/usr/bin/env python3
"""历史成交手续费回补（stage 2026-08-19-hedge-order-fee-cost-v1 T3，10-design §4.3）。

独立一次性脚本：不挂下单/平仓/drain/worker/启动闸门，服务启动不自动跑。
对实盘数据库执行带网络外发的 live 回补**须 Human 明确授权**；本脚本绝不
改写 ``hedge_open_cycle_close_log`` 旧行（断点 1），不改腿的成交终态。

范围：``hedge_open_leg`` 中 ``exchange_status=FILLED``、``order_id`` 非空、
冻结四列全空的腿（开仓/平仓都补）。按 ``id`` 升序推进，断点落
``--progress``（默认 ``data/backfill-leg-fees-progress.json``）：已写入跳过、
已尝试失败的重跑不再打（省签名配额）。签名 GET ≤1 次/秒；429/418 立刻停。
有 running 对冲任务时拒绝启动。BNB 冻价取成交时刻公开 ``BNBUSDT`` 1m K 线
收盘价（无签名接口，与签名配额分开）。

用法（在仓库根目录）：
  python3 scripts/backfill-leg-fees.py --dry-run     # 零网络零写入，只列候选
  python3 scripts/backfill-leg-fees.py --limit 20    # 试跑 20 条
  python3 scripts/backfill-leg-fees.py               # 全量（须 Human 授权）

退出码：0 正常收尾；1 拒绝启动（running 任务 / 离线配置 / 无凭证）；
2 因 429/418 限速中断（断点已保存，冷却后重跑）。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.adapters.binance_public import BinancePublicClient
from backend.config import from_env
from backend.hedge_open_tasks import fee_fetcher as FF
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.services.hedge_open_live_client import HedgeOpenLiveClient

DEFAULT_DB = REPO_ROOT / "data" / "hedge-open-tasks.sqlite3"
DEFAULT_PROGRESS = REPO_ROOT / "data" / "backfill-leg-fees-progress.json"


def _unwrap_list(resp) -> list:
    """签名 GET 响应 → 成交列表。429/418 → RateLimited（整轮停）；其余非
    200/非列表 → FeeFetchError（该腿失败，不重试）。"""
    if resp.http_status in (429, 418):
        raise FF.RateLimited(resp.http_status)
    if resp.http_status != 200 or not isinstance(resp.body, list):
        body = str(resp.body)[:120] if resp.body is not None else resp.transport_error
        raise FF.FeeFetchError(f"http={resp.http_status} body={body}")
    return resp.body


def build_transport(config, client: HedgeOpenLiveClient,
                    public: BinancePublicClient) -> FF.FeeTransport:
    """装配注入式传输：签名成交明细 ×3 + 公开 BNB 1m K 线冻价。"""

    def spot_trades(symbol, order_id, limit):
        return _unwrap_list(client.get_spot_my_trades(
            symbol, order_id, limit=limit, timestamp_ms=int(time.time() * 1000)))

    def margin_trades(symbol, order_id, limit):
        return _unwrap_list(client.get_margin_my_trades(
            symbol, order_id, limit=limit, timestamp_ms=int(time.time() * 1000)))

    def um_trades(symbol, start_ms, end_ms, limit):
        return _unwrap_list(client.get_um_user_trades(
            symbol, start_time_ms=start_ms, end_time_ms=end_ms, limit=limit,
            timestamp_ms=int(time.time() * 1000)))

    def bnb_close_price(start_ms):
        try:
            return public.fetch_kline_close("BNBUSDT", start_time_ms=start_ms)
        except Exception:
            # 公开 K 线失败只降级价格（数量仍写、该腿不全），不阻塞回补。
            return None

    return FF.FeeTransport(
        spot_trades=spot_trades,
        margin_trades=margin_trades,
        um_trades=um_trades,
        bnb_close_price=bnb_close_price,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="历史成交手续费回补（T3；live 执行须 Human 明确授权）")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="hedge-open 库路径")
    parser.add_argument("--progress", default=str(DEFAULT_PROGRESS),
                        help="断点文件路径（游标 + 已失败集合）")
    parser.add_argument("--limit", type=int, default=None,
                        help="本轮最多处理的腿数（试跑保护）")
    parser.add_argument("--dry-run", action="store_true",
                        help="零网络零写入，只列候选腿")
    args = parser.parse_args(argv)

    config = from_env()
    if args.dry_run:
        store = HedgeOpenStore(args.db)
        try:
            engine = FF.BackfillEngine(
                store=store, transport=None, progress_path=args.progress)
            summary = engine.run(dry_run=True)
        finally:
            store.close()
        print(f"[dry-run] 候选腿 {len(summary['planned_legs'])} 条："
              f"{summary['planned_legs'][:50]}"
              f"{'…' if len(summary['planned_legs']) > 50 else ''}")
        print(f"[dry-run] 游标 {summary['cursor']}（不推进、不写断点）")
        return 0

    if config.offline:
        print("拒绝启动：APP_OFFLINE=true（live 回补必须联网配置）", file=sys.stderr)
        return 1
    if not (config.binance_hedge_api_key and config.binance_hedge_api_secret):
        print("拒绝启动：缺 BINANCE_HEDGE_API_KEY / SECRET", file=sys.stderr)
        return 1

    client = HedgeOpenLiveClient(
        config.binance_hedge_api_key,
        config.binance_hedge_api_secret,
        user_agent=config.user_agent,
    )
    public = BinancePublicClient(
        offline=False,
        offline_dir=config.offline_raw_dir,
        futures_base_url=config.futures_base_url,
        spot_base_url=config.spot_base_url,
        user_agent=config.user_agent,
        timeout=config.request_timeout,
    )
    transport = build_transport(config, client, public)
    store = HedgeOpenStore(args.db)
    try:
        engine = FF.BackfillEngine(
            store=store, transport=transport, progress_path=args.progress,
            sleep=time.sleep)
        summary = engine.run(max_legs=args.limit)
    finally:
        store.close()

    if summary["refused"]:
        print(f"拒绝启动：{summary['refused']}（有 running 对冲任务时不回补）",
              file=sys.stderr)
        return 1
    print(
        f"回补收尾：尝试 {summary['attempted']}｜写入 {summary['written']}"
        f"（其中列不完整 {summary['written_incomplete']}）｜判定失败 "
        f"{summary['failed']}｜游标 {summary['cursor']}"
    )
    if summary["reasons"]:
        print(f"失败原因分布：{summary['reasons']}")
    if summary["stopped"]:
        print(f"限速中断：{summary['stopped']}——断点已保存，冷却后重跑即可续作",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
