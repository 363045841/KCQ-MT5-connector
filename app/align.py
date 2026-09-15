# 时区对齐纯函数：4h/日线自 H1、周/月自 D1 按锚时区重采样（无 MT5 依赖，pytest 直接覆盖）。
#
# 锚规则（对齐决策）：
# - 加密品种 → UTC 自然边界（币安标准）
# - 传统品种（外汇/金属/指数等）→ Europe/Athens（EET/EEST 自动 DST），周日短棒自然并入周一首根
# - ALIGN_TZ=gmt2/gmt3 → 传统品种改用固定偏移锚（env 覆盖）

from __future__ import annotations

from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from .frames import Bar

ATHENS = ZoneInfo("Europe/Athens")
GMT2 = timezone(timedelta(hours=2))
GMT3 = timezone(timedelta(hours=3))

# 支持对齐重采样的目标周期：4h/日线取自 H1，周/月取自 D1
RESAMPLE_H1_TARGETS = frozenset({"4h", "daily"})
RESAMPLE_D1_TARGETS = frozenset({"weekly", "monthly"})


def anchor_tz(asset_class: str, align_mode: str):
    """按品种类别与对齐模式解析锚时区；仅在对齐开启时被调用。"""
    if asset_class == "crypto":
        return timezone.utc
    if align_mode == "gmt2":
        return GMT2
    if align_mode == "gmt3":
        return GMT3
    return ATHENS


def server_to_utc_ms(server_ms: int, offset_minutes: int) -> int:
    """服务器伪 UTC 毫秒 → 真 UTC 毫秒（offset 为服务器领先 UTC 的分钟数）。"""
    return int(server_ms) - offset_minutes * 60_000


def _bin_starts(index_utc: pd.DatetimeIndex, anchor, target: str) -> pd.DatetimeIndex:
    """把 UTC 时间索引换算到锚时区并计算每个样本所属桶的本地起始时刻（naive）。

    - daily：自然日 00:00；4h：自然日 + hour//4*4 时段
    - weekly：ISO 周锚（周一 00:00）；monthly：自然月 1 日 00:00
    """
    local = index_utc.tz_convert(anchor).tz_localize(None)
    if target == "daily":
        return local.normalize()
    if target == "4h":
        return local.normalize() + pd.to_timedelta(local.hour // 4 * 4, unit="h")
    if target == "weekly":
        return local.normalize() - pd.to_timedelta(local.weekday, unit="D")
    if target == "monthly":
        return local.to_period("M").start_time
    raise ValueError(f"unsupported resample target: {target!r}")


def resample(bars: list[Bar], target: str, anchor, offset_minutes: int) -> list[Bar]:
    """把服务器时间 H1/D1 序列重采样为 4h/daily/weekly/monthly，输出真 UTC Bar。

    输入必须升序；输出时间戳为锚时区边界对应的 UTC 毫秒，OHLCV 按桶聚合。
    """
    if not bars:
        return []

    index_utc = pd.DatetimeIndex(
        pd.to_datetime(
            [server_to_utc_ms(b.time_ms, offset_minutes) for b in bars], unit="ms", utc=True
        )
    )
    frame = pd.DataFrame(
        {
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
            "turnover": [b.turnover for b in bars],
        },
        index=index_utc,
    ).sort_index()

    grouped = frame.groupby(_bin_starts(index_utc, anchor, target)).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        turnover=("turnover", "sum"),
    )
    # 桶起始（本地墙钟）→ 锚时区 → UTC 毫秒；00:00/04:00 等边界不落在 DST 切换窗内。
    # pandas 2.x：tz-aware 索引不能直接 astype 数值/naive，先去 tz 再统一 ns 精度取整。
    starts_utc_ns = (
        grouped.index.tz_localize(anchor).tz_convert("UTC").tz_localize(None)
    ).astype("datetime64[ns]").astype("int64")
    out_ms = starts_utc_ns // 10**6
    return [
        Bar(
            time_ms=int(out_ms[i]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            turnover=float(row["turnover"]),
        )
        for i, (_, row) in enumerate(grouped.iterrows())
    ]
